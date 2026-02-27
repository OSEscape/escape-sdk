"""Graph Pathfinder - Dijkstra on pre-computed skeleton + transport graph (NPZ/CSR format)."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import numpy as np

from escape.pathfinding.core.world_point import pack_world_point
from escape.pathfinding.pathfinder.detailed_pathfinding import _build_detailed_from_graph_result
from escape.pathfinding.pathfinder.detailed_pathfinding import (
    find_path_detailed as _find_path_detailed,
)
from escape.pathfinding.pathfinder.dijkstra_jit import _dijkstra_csr, _dijkstra_csr_multi_target
from escape.pathfinding.pathfinder.path_result_builder import (
    build_path_steps,
    build_segments,
    extract_transports_from_steps,
    get_edge_transport_info,
    get_transport_name,
)
from escape.pathfinding.pathfinder.path_types import (
    DetailedPathResult,
    PathResult,
    PathStep,
    Segment,
)

if TYPE_CHECKING:
    from pathlib import Path

    from escape.pathfinding.core.enums import TransportType
    from escape.pathfinding.core.player_context import PlayerContext
    from escape.pathfinding.pathfinder.numba_pathfinder import NumbaPathfinder
    from escape.pathfinding.pathfinder.transport_metadata import (
        TransportMetadata,
        TransportMetadataDB,
    )
    from escape.pathfinding.transport.transport import Transport

logger = logging.getLogger(__name__)

_TELEPORT_FALLBACK_COST = 10_000_000


def _ticks_to_tiles(ticks: int) -> int:
    """Convert game ticks to tiles-equivalent cost (must match graph builder)."""
    return (ticks * 2) + 4


def _item_signature(items: object | None) -> tuple[object, ...] | None:
    """Create a hashable signature for item requirements."""
    if items is None:
        return None
    from escape.pathfinding.transport.transport import TransportItems

    assert isinstance(items, TransportItems)
    return (
        tuple(tuple(x) if x else () for x in items.items),
        tuple(tuple(x) if x else () for x in items.staves),
        tuple(tuple(x) if x else () for x in items.offhands),
        tuple(items.quantities),
    )


class GraphPathfinder:
    """High-performance pathfinder using pre-computed connectivity graph (NPZ + CSR)."""

    __slots__ = (
        "_empty_blocked",
        "_plane_graph_node_ids",
        "_plane_graph_packed",
        "_quest_only_groups",
        "_req_signature_groups",
        "_skill_only_groups",
        "_type_edge_indices",
        "bank_node_ids",
        "edge_offsets",
        "edge_targets",
        "edge_transport_type",
        "edge_transports",
        "edge_weights",
        "edges_with_req",
        "graph_node_ids",
        "graph_packed",
        "metadata_db",
        "node_is_skeleton",
        "node_is_spawn",
        "node_names",
        "node_plane",
        "node_x",
        "node_y",
        "num_nodes",
        "num_skeleton",
        "numba_pathfinder",
        "skeleton_node_ids",
        "skeleton_packed",
        "spawn_costs",
        "spawn_node_ids",
        "spawn_transports",
    )

    def __init__(
        self,
        node_x: np.ndarray,
        node_y: np.ndarray,
        node_plane: np.ndarray,
        node_is_skeleton: np.ndarray,
        node_is_spawn: np.ndarray,
        node_names: np.ndarray,
        num_skeleton: int,
        num_nodes: int,
        edge_offsets: np.ndarray,
        edge_targets: np.ndarray,
        edge_weights: np.ndarray,
        edge_transport_type: np.ndarray,
        skeleton_packed: np.ndarray,
        skeleton_node_ids: np.ndarray,
        graph_packed: np.ndarray,
        graph_node_ids: np.ndarray,
        spawn_node_ids: np.ndarray,
        spawn_costs: np.ndarray,
        edges_with_req: np.ndarray,
        bank_node_ids: np.ndarray,
        edge_transports: dict[int, Transport],
        spawn_transports: dict[int, list[Transport]],
        metadata_db: TransportMetadataDB | None,
        numba_pathfinder: NumbaPathfinder,
    ):
        self.node_x = node_x
        self.node_y = node_y
        self.node_plane = node_plane
        self.node_is_skeleton = node_is_skeleton
        self.node_is_spawn = node_is_spawn
        self.node_names = node_names
        self.num_skeleton = num_skeleton
        self.num_nodes = num_nodes
        self.edge_offsets = edge_offsets
        self.edge_targets = edge_targets
        self.edge_weights = edge_weights
        self.edge_transport_type = edge_transport_type
        self.skeleton_packed = skeleton_packed
        self.skeleton_node_ids = skeleton_node_ids
        self.graph_packed = graph_packed
        self.graph_node_ids = graph_node_ids
        self.spawn_node_ids = spawn_node_ids
        self.spawn_costs = spawn_costs
        self.edges_with_req = edges_with_req
        self.bank_node_ids = bank_node_ids
        self.edge_transports = edge_transports
        self.spawn_transports = spawn_transports
        self.metadata_db = metadata_db
        self.numba_pathfinder = numba_pathfinder

        # Pre-allocate empty blocked array (all False) for maxed player
        self._empty_blocked = np.zeros(len(edge_targets), dtype=np.bool_)

        # Pre-group edges by requirement type for bulk checking
        quest_groups: dict[str, list[int]] = {}
        skill_groups: dict[tuple[str, int], list[int]] = {}
        # Signature-based dedup: edges with identical requirements share one check
        sig_groups: dict[tuple[object, ...], list[int]] = {}
        sig_transport: dict[tuple[object, ...], int] = {}  # sig → representative edge_idx

        for edge_idx in edges_with_req:
            transport = edge_transports.get(int(edge_idx))
            if transport is None:
                continue
            has_skills = bool(transport.skill_levels)
            has_quests = bool(transport.quests)
            has_varbits = bool(transport.varbits)
            has_varplayers = bool(transport.varplayers)
            has_items = bool(transport.item_requirements)
            n_types = has_skills + has_quests + has_varbits + has_varplayers + has_items

            if n_types == 1 and has_quests and len(transport.quests) == 1:
                quest_name = next(iter(transport.quests))
                quest_groups.setdefault(quest_name, []).append(int(edge_idx))
            elif n_types == 1 and has_skills and len(transport.skill_levels) == 1:
                skill, level = next(iter(transport.skill_levels.items()))
                skill_groups.setdefault((skill.upper(), level), []).append(int(edge_idx))
            else:
                # Compute hashable requirement signature
                sig: tuple[object, ...] = (
                    frozenset(transport.skill_levels.items()),
                    frozenset(transport.quests),
                    frozenset((v.varbit_id, v.value, v.check_type) for v in transport.varbits),
                    frozenset(
                        (v.varplayer_id, v.value, v.check_type) for v in transport.varplayers
                    ),
                    _item_signature(transport.item_requirements),
                )
                sig_groups.setdefault(sig, []).append(int(edge_idx))
                if sig not in sig_transport:
                    sig_transport[sig] = int(edge_idx)

        self._quest_only_groups: dict[str, np.ndarray] = {
            k: np.array(v, dtype=np.intp) for k, v in quest_groups.items()
        }
        self._skill_only_groups: dict[tuple[str, int], np.ndarray] = {
            k: np.array(v, dtype=np.intp) for k, v in skill_groups.items()
        }
        # List of (representative_transport, edge_indices) for signature-deduped groups
        self._req_signature_groups: list[tuple[Transport, np.ndarray]] = [
            (edge_transports[sig_transport[sig]], np.array(indices, dtype=np.intp))
            for sig, indices in sig_groups.items()
        ]

        # Pre-compute edge indices per TransportType from Transport objects (ground truth).
        # The NPZ edge_transport_type codes may use a different enum ordering than the
        # current TransportType enum, so we derive the mapping from the pickle data.
        type_edges: dict[TransportType, list[int]] = {}
        for edge_idx, transport in edge_transports.items():
            type_edges.setdefault(transport.transport_type, []).append(int(edge_idx))
        self._type_edge_indices: dict[TransportType, np.ndarray] = {
            tt: np.array(indices, dtype=np.intp) for tt, indices in type_edges.items()
        }

        # Pre-compute per-plane graph arrays for fast lookup
        self._plane_graph_packed: dict[int, np.ndarray] = {}
        self._plane_graph_node_ids: dict[int, np.ndarray] = {}
        for plane in range(4):
            plane_mask = self.node_plane[self.graph_node_ids] == plane
            self._plane_graph_packed[plane] = np.ascontiguousarray(self.graph_packed[plane_mask])
            self._plane_graph_node_ids[plane] = np.ascontiguousarray(
                self.graph_node_ids[plane_mask]
            )

    @classmethod
    def from_directory(cls, output_dir: str | Path) -> GraphPathfinder:
        """Load GraphPathfinder from output directory containing graph.npz and transports.pkl."""
        from escape.pathfinding.pathfinder.graph_loader import load_graph_pathfinder

        return load_graph_pathfinder(output_dir)

    def find_path(
        self,
        start: tuple[int, int, int],
        goal: tuple[int, int, int],
        player_context: PlayerContext | None = None,
        use_teleports: bool = True,
        use_bank_items: bool = True,
        disabled_types: frozenset[TransportType] | None = None,
        max_iterations: int = 1000000,
    ) -> PathResult:
        """Find optimal path from start to goal."""
        t0 = time.perf_counter()

        start_x, start_y, start_z = start
        goal_x, goal_y, goal_z = goal

        # BFS from start to find nearest graph node (also checks direct walk to goal)
        plane_graph_packed = self._plane_graph_packed.get(start_z)
        plane_graph_node_ids = self._plane_graph_node_ids.get(start_z)

        if plane_graph_packed is None or len(plane_graph_packed) == 0:
            return PathResult(found=False)

        goal_packed = pack_world_point(goal_x, goal_y, goal_z)
        if start_z == goal_z:
            goal_idx = np.searchsorted(plane_graph_packed, goal_packed)
            combined_targets = np.insert(plane_graph_packed, goal_idx, goal_packed)
        else:
            combined_targets = plane_graph_packed

        start_found_packed, start_walk_cost, start_found = (
            self.numba_pathfinder.find_nearest_target(
                start_x, start_y, start_z, combined_targets, max_iterations=50000
            )
        )

        t_bfs_start = time.perf_counter()

        # Teleport fallback: when start BFS fails (disconnected area) and teleports
        # are enabled, treat the search as starting from node 0 with a large penalty
        # so that teleport-first routes are still discoverable.
        is_teleport_fallback = False
        if not start_found:
            if not use_teleports:
                return PathResult(found=False)
            is_teleport_fallback = True
            start_node = 0
            start_walk_cost = _TELEPORT_FALLBACK_COST
        else:
            # Direct walk to goal - no graph needed (skip in fallback mode)
            if start_z == goal_z and start_found_packed == goal_packed:
                steps = [
                    PathStep(x=start_x, y=start_y, plane=start_z, node_id=-1, step_type="start"),
                    PathStep(x=goal_x, y=goal_y, plane=goal_z, node_id=-2, step_type="goal"),
                ]
                return PathResult(
                    found=True,
                    total_cost=start_walk_cost,
                    steps=steps,
                    segments=self._build_segments(steps),
                    transports_used=[],
                    walk_distance=start_walk_cost,
                    iterations=0,
                )

            # Map packed position back to node ID
            idx = np.searchsorted(plane_graph_packed, start_found_packed)
            if idx >= len(plane_graph_packed) or plane_graph_packed[idx] != start_found_packed:
                return PathResult(found=False)
            assert plane_graph_node_ids is not None
            start_node = plane_graph_node_ids[idx]

        # BFS from goal to find nearest graph node
        goal_plane_graph_packed = self._plane_graph_packed.get(goal_z)
        goal_plane_graph_node_ids = self._plane_graph_node_ids.get(goal_z)

        if goal_plane_graph_packed is None or len(goal_plane_graph_packed) == 0:
            return PathResult(found=False)

        goal_found_packed, goal_walk_cost, goal_found = self.numba_pathfinder.find_nearest_target(
            goal_x, goal_y, goal_z, goal_plane_graph_packed, max_iterations=50000
        )

        t_bfs_goal = time.perf_counter()

        if not goal_found:
            return PathResult(found=False)

        idx = np.searchsorted(goal_plane_graph_packed, goal_found_packed)
        if idx >= len(goal_plane_graph_packed) or goal_plane_graph_packed[idx] != goal_found_packed:
            return PathResult(found=False)
        assert goal_plane_graph_node_ids is not None
        goal_node = goal_plane_graph_node_ids[idx]

        # Short-circuit: both BFS reach the same graph node (skip in fallback mode)
        if not is_teleport_fallback and start_node == goal_node:
            total_cost = start_walk_cost + goal_walk_cost
            skel_x = int(self.node_x[start_node])
            skel_y = int(self.node_y[start_node])
            skel_plane = int(self.node_plane[start_node])

            steps = [
                PathStep(x=start[0], y=start[1], plane=start[2], node_id=-1, step_type="start"),
                PathStep(
                    x=skel_x, y=skel_y, plane=skel_plane, node_id=start_node, step_type="walk"
                ),
                PathStep(x=goal[0], y=goal[1], plane=goal[2], node_id=-2, step_type="goal"),
            ]
            return PathResult(
                found=True,
                total_cost=total_cost,
                steps=steps,
                segments=self._build_segments(steps),
                transports_used=[],
                walk_distance=total_cost,
                iterations=0,
            )

        # Prepare Dijkstra: filter edges and build virtual teleport edges
        t_prep_start = time.perf_counter()
        empty_i32 = np.array([], dtype=np.int32)

        if player_context is None and not disabled_types:
            edge_blocked = self._empty_blocked
            edge_bank_unblockable = self._empty_blocked
        else:
            edge_blocked, edge_bank_unblockable = self._compute_blocked_and_bank_unblockable(
                player_context, disabled_types, use_bank_items
            )

        t_blocked_done = time.perf_counter()

        matched_spawns: dict[int, Transport] = {}

        if not use_teleports:
            virtual_targets = empty_i32
            virtual_weights = empty_i32
            bank_virtual_targets = empty_i32
            bank_virtual_weights = empty_i32
        elif player_context is None and not disabled_types:
            virtual_targets = self.spawn_node_ids
            virtual_weights = self.spawn_costs.astype(np.int32)
            bank_virtual_targets = empty_i32
            bank_virtual_weights = empty_i32
        else:
            (
                virtual_targets,
                virtual_weights,
                bank_virtual_targets,
                bank_virtual_weights,
                matched_spawns,
            ) = self._filter_all_spawn_points(player_context, disabled_types, use_bank_items)

        t_filter_done = time.perf_counter()

        bank_node_ids = self.bank_node_ids if use_bank_items else empty_i32

        # Run Dijkstra
        dist, prev, iterations, found = _dijkstra_csr(
            start_node,
            goal_node,
            self.edge_offsets,
            self.edge_targets,
            self.edge_weights,
            virtual_targets,
            virtual_weights,
            start_walk_cost,
            edge_blocked,
            bank_node_ids,
            bank_virtual_targets,
            bank_virtual_weights,
            edge_bank_unblockable,
            max_iterations,
        )

        t_dijkstra_done = time.perf_counter()

        if not found:
            return PathResult(found=False, iterations=iterations)

        # Reconstruct path and build result
        total_cost = int(dist[goal_node]) + goal_walk_cost
        path_nodes = self._reconstruct_path(prev, goal_node)

        # Only show bank steps when there are bank-unlockable items/edges to pick up
        has_bank_unlocks = len(bank_virtual_targets) > 0 or np.any(edge_bank_unblockable)
        bank_nodes = set(bank_node_ids.tolist()) if has_bank_unlocks else None
        steps = self._build_steps(path_nodes, start, goal, prev, bank_nodes)

        # Override transport names for spawn nodes with the specific matched transport
        if matched_spawns:
            for step in steps:
                if step.step_type in ("teleport",) and step.node_id in matched_spawns:
                    matched = matched_spawns[step.node_id]
                    if matched.display_info:
                        step.transport_name = matched.display_info

        segments = self._build_segments(steps)
        transports_used, transports_metadata = self._extract_transports(steps)

        t_end = time.perf_counter()

        # In fallback mode, walk_distance is only the goal-side walk
        walk_distance = goal_walk_cost if is_teleport_fallback else start_walk_cost + goal_walk_cost

        logger.debug(
            "find_path timing: bfs_start=%.2fms bfs_goal=%.2fms "
            "blocked=%.2fms spawns=%.2fms dijkstra=%.2fms reconstruct=%.2fms total=%.2fms | "
            "edges_with_req=%d spawn_nodes=%d iterations=%d teleport_fallback=%s",
            (t_bfs_start - t0) * 1000,
            (t_bfs_goal - t_bfs_start) * 1000,
            (t_blocked_done - t_prep_start) * 1000,
            (t_filter_done - t_blocked_done) * 1000,
            (t_dijkstra_done - t_filter_done) * 1000,
            (t_end - t_dijkstra_done) * 1000,
            (t_end - t0) * 1000,
            len(self.edges_with_req),
            len(self.spawn_node_ids),
            iterations,
            is_teleport_fallback,
        )

        return PathResult(
            found=True,
            total_cost=total_cost,
            steps=steps,
            segments=segments,
            transports_used=transports_used,
            transports_metadata=transports_metadata,
            walk_distance=walk_distance,
            iterations=iterations,
            matched_spawns=matched_spawns,
        )

    def _compute_blocked_and_bank_unblockable(
        self,
        ctx: PlayerContext | None,
        disabled_types: frozenset[TransportType] | None = None,
        use_bank_items: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute blocked edges and which blocked edges a bank visit would unblock."""
        from escape.pathfinding.transport.transport import _check_type_requirements

        n_edges = len(self.edge_targets)
        blocked = np.zeros(n_edges, dtype=np.bool_)
        bank_unblockable = np.zeros(n_edges, dtype=np.bool_)

        if ctx is not None:
            # Bulk quest-only edge checks (31 quest lookups vs 1016 method calls)
            for quest_name, edge_indices in self._quest_only_groups.items():
                if not ctx.has_completed_quest(quest_name):
                    blocked[edge_indices] = True
                    # Bank can't help with quest failures

            # Bulk skill-only edge checks
            for (skill, level), edge_indices in self._skill_only_groups.items():
                if ctx.skill_levels.get(skill, 0) < level:
                    blocked[edge_indices] = True
                    # Bank can't help with skill failures

            # Signature-deduped checks: one eval per unique requirement set
            for transport, edge_indices in self._req_signature_groups:
                if not transport.meets_requirements(ctx, assume_items=True, _skip_type_check=True):
                    # Failed on skills/quests/varbits — bank can't help
                    blocked[edge_indices] = True
                elif transport.item_requirements and not transport._check_item_requirements(
                    ctx, check_bank=False
                ):
                    # Non-item reqs passed but items failed — bank might help
                    blocked[edge_indices] = True
                    if use_bank_items and transport._check_item_requirements(ctx, check_bank=True):
                        bank_unblockable[edge_indices] = True

            # Type-level requirement checks (fairy rings, gnome gliders, etc.)
            for tt, indices in self._type_edge_indices.items():
                if not _check_type_requirements(tt, ctx):
                    blocked[indices] = True
                    if use_bank_items and _check_type_requirements(tt, ctx, check_bank=True):
                        bank_unblockable[indices] = True

        if disabled_types:
            for tt in disabled_types:
                indices = self._type_edge_indices.get(tt)
                if indices is not None:
                    blocked[indices] = True

        return blocked, bank_unblockable

    def _filter_all_spawn_points(
        self,
        ctx: PlayerContext | None,
        disabled_types: frozenset[TransportType] | None,
        use_bank_items: bool,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[int, Transport]]:
        """Single-pass spawn filtering: classify each spawn as available or bank-unblockable.

        Each spawn node may have multiple Transport objects (e.g. spell + tablet to same
        destination). A spawn is available if ANY of its transports meets requirements.

        Returns (available_ids, available_costs, bank_ids, bank_costs, matched_transports).
        The matched_transports dict maps spawn node_id -> first Transport that qualified.
        """
        available_ids: list[int] = []
        available_costs: list[int] = []
        bank_ids: list[int] = []
        bank_costs: list[int] = []
        matched: dict[int, Transport] = {}

        for i, spawn_id in enumerate(self.spawn_node_ids):
            transports = self.spawn_transports.get(int(spawn_id))

            if transports is not None:
                # Filter out disabled transport types
                active = transports
                if disabled_types:
                    active = [t for t in transports if t.transport_type not in disabled_types]
                if not active:
                    continue

                if ctx is not None:
                    # Available if ANY active transport meets requirements — pick cheapest
                    matches = [t for t in active if t.meets_requirements(ctx)]
                    if matches:
                        match = min(matches, key=lambda t: t.duration)
                        available_ids.append(spawn_id)
                        available_costs.append(_ticks_to_tiles(match.duration))
                        matched[int(spawn_id)] = match
                    elif use_bank_items:
                        bank_matches = [
                            t
                            for t in active
                            if t.meets_requirements(ctx, assume_items=True)
                            and t.item_requirements
                            and t._check_item_requirements(ctx, check_bank=True)
                        ]
                        if bank_matches:
                            bank_match = min(bank_matches, key=lambda t: t.duration)
                            bank_ids.append(spawn_id)
                            bank_costs.append(_ticks_to_tiles(bank_match.duration))
                            matched[int(spawn_id)] = bank_match
                else:
                    cheapest = min(active, key=lambda t: t.duration)
                    available_ids.append(spawn_id)
                    available_costs.append(_ticks_to_tiles(cheapest.duration))
                    matched[int(spawn_id)] = cheapest
            else:
                # No Transport objects stored — include unless type-disabled via metadata
                if disabled_types and self.metadata_db is not None:
                    meta_list = self.metadata_db.get(int(spawn_id))
                    if meta_list is not None:
                        meta_type_name = meta_list[0].transport_type
                        if any(dt.name == meta_type_name for dt in disabled_types):
                            continue
                available_ids.append(spawn_id)
                available_costs.append(self.spawn_costs[i])

        return (
            np.array(available_ids, dtype=np.int32),
            np.array(available_costs, dtype=np.int32),
            np.array(bank_ids, dtype=np.int32),
            np.array(bank_costs, dtype=np.int32),
            matched,
        )

    def _reconstruct_path(self, prev: np.ndarray, goal_node: int) -> list[int]:
        """Reconstruct path from predecessor array."""
        path = []
        node = goal_node

        while node >= 0:
            path.append(node)
            node = prev[node]

        path.reverse()
        return path

    def _build_steps(
        self,
        path_nodes: list[int],
        start: tuple[int, int, int],
        goal: tuple[int, int, int],
        prev: np.ndarray,
        bank_nodes: set[int] | None = None,
    ) -> list[PathStep]:
        """Build PathStep list from node path. Delegates to path_result_builder."""
        return build_path_steps(
            path_nodes,
            start,
            goal,
            prev,
            self.node_x,
            self.node_y,
            self.node_plane,
            self.node_names,
            self.edge_offsets,
            self.edge_targets,
            self.edge_transport_type,
            bank_nodes,
            self.edge_transports,
        )

    def _get_transport_name(self, node_id: int) -> str | None:
        """Get transport name for a node."""
        return get_transport_name(node_id, self.node_names)

    def _get_edge_transport_type(self, from_node: int, to_node: int) -> int:
        """Get the transport type of the edge from from_node to to_node."""
        edge_type, _csr_idx = get_edge_transport_info(
            from_node, to_node, self.edge_offsets, self.edge_targets, self.edge_transport_type
        )
        return edge_type

    def get_transport_metadata(self, node_id: int) -> list[TransportMetadata] | None:
        """Get metadata list for a transport node."""
        if self.metadata_db is not None:
            return self.metadata_db.get(node_id)
        return None

    def get_edge_transport(self, from_node: int, to_node: int) -> Transport | None:
        """Get the Transport object for the edge from from_node to to_node."""
        start_idx = self.edge_offsets[from_node]
        end_idx = self.edge_offsets[from_node + 1]
        for j in range(start_idx, end_idx):
            if self.edge_targets[j] == to_node:
                return self.edge_transports.get(int(j))
        return None

    def _build_segments(self, steps: list[PathStep]) -> list[Segment]:
        """Build segments from steps. Delegates to path_result_builder."""
        return build_segments(steps)

    def _extract_transports(
        self, steps: list[PathStep]
    ) -> tuple[list[str], list[TransportMetadata]]:
        """Extract transport names and metadata from steps."""
        return extract_transports_from_steps(steps, self.metadata_db, self.edge_transports)

    def find_path_detailed(
        self,
        start: tuple[int, int, int],
        goal: tuple[int, int, int],
        player_context: PlayerContext | None = None,
        use_teleports: bool = True,
        use_bank_items: bool = True,
        disabled_types: frozenset[TransportType] | None = None,
        ellipse_margin: float = 1.2,
        max_segment_iterations: int = 100000,
    ) -> DetailedPathResult:
        """Find path with actual tile-by-tile details using hybrid approach."""
        return _find_path_detailed(
            self,
            start,
            goal,
            player_context,
            use_teleports,
            use_bank_items,
            disabled_types,
            ellipse_margin,
            max_segment_iterations,
        )

    def find_nearest_bank(
        self,
        start: tuple[int, int, int],
        player_context: PlayerContext | None = None,
        use_teleports: bool = True,
        disabled_types: frozenset[TransportType] | None = None,
        max_iterations: int = 1000000,
    ) -> PathResult:
        """Find optimal path from start to the nearest bank."""
        t0 = time.perf_counter()

        start_x, start_y, start_z = start

        if len(self.bank_node_ids) == 0:
            return PathResult(found=False)

        # BFS from start to find nearest graph node
        plane_graph_packed = self._plane_graph_packed.get(start_z)
        plane_graph_node_ids = self._plane_graph_node_ids.get(start_z)

        is_teleport_fallback = False

        if plane_graph_packed is None or len(plane_graph_packed) == 0:
            if not use_teleports:
                return PathResult(found=False)
            is_teleport_fallback = True
            start_node = 0
            start_walk_cost = _TELEPORT_FALLBACK_COST
        else:
            start_found_packed, start_walk_cost, start_found = (
                self.numba_pathfinder.find_nearest_target(
                    start_x, start_y, start_z, plane_graph_packed, max_iterations=50000
                )
            )

            if not start_found:
                if not use_teleports:
                    return PathResult(found=False)
                is_teleport_fallback = True
                start_node = 0
                start_walk_cost = _TELEPORT_FALLBACK_COST
            else:
                idx = np.searchsorted(plane_graph_packed, start_found_packed)
                if idx >= len(plane_graph_packed) or plane_graph_packed[idx] != start_found_packed:
                    return PathResult(found=False)
                assert plane_graph_node_ids is not None
                start_node = plane_graph_node_ids[idx]

        t_bfs_start = time.perf_counter()

        # Prepare Dijkstra: filter edges and build virtual teleport edges
        empty_i32 = np.array([], dtype=np.int32)

        if player_context is None and not disabled_types:
            edge_blocked = self._empty_blocked
        else:
            edge_blocked, _ = self._compute_blocked_and_bank_unblockable(
                player_context, disabled_types, use_bank_items=False
            )

        matched_spawns: dict[int, Transport] = {}

        if not use_teleports:
            virtual_targets = empty_i32
            virtual_weights = empty_i32
        elif player_context is None and not disabled_types:
            virtual_targets = self.spawn_node_ids
            virtual_weights = self.spawn_costs.astype(np.int32)
        else:
            (
                virtual_targets,
                virtual_weights,
                _bank_vt,
                _bank_vw,
                matched_spawns,
            ) = self._filter_all_spawn_points(player_context, disabled_types, use_bank_items=False)

        t_filter_done = time.perf_counter()

        # Run multi-target Dijkstra
        dist, prev, iterations, found, found_node = _dijkstra_csr_multi_target(
            start_node,
            self.bank_node_ids,
            self.edge_offsets,
            self.edge_targets,
            self.edge_weights,
            virtual_targets,
            virtual_weights,
            start_walk_cost,
            edge_blocked,
            max_iterations,
        )

        t_dijkstra_done = time.perf_counter()

        if not found:
            return PathResult(found=False, iterations=iterations)

        # Reconstruct path to the found bank node
        total_cost = int(dist[found_node])
        path_nodes = self._reconstruct_path(prev, found_node)

        # Build goal from the found bank node coords
        bank_x = int(self.node_x[found_node])
        bank_y = int(self.node_y[found_node])
        bank_plane = int(self.node_plane[found_node])
        goal = (bank_x, bank_y, bank_plane)

        steps = self._build_steps(path_nodes, start, goal, prev)

        # Override last step type to "bank"
        if steps:
            steps[-1] = PathStep(
                x=bank_x,
                y=bank_y,
                plane=bank_plane,
                node_id=found_node,
                step_type="bank",
            )

        # Override transport names for spawn nodes with the specific matched transport
        if matched_spawns:
            for step in steps:
                if step.step_type in ("teleport",) and step.node_id in matched_spawns:
                    matched = matched_spawns[step.node_id]
                    if matched.display_info:
                        step.transport_name = matched.display_info

        segments = self._build_segments(steps)
        transports_used, transports_metadata = self._extract_transports(steps)

        walk_distance = 0 if is_teleport_fallback else start_walk_cost

        t_end = time.perf_counter()

        logger.debug(
            "find_nearest_bank timing: bfs_start=%.2fms "
            "filter=%.2fms dijkstra=%.2fms reconstruct=%.2fms total=%.2fms | "
            "iterations=%d found_node=%d teleport_fallback=%s",
            (t_bfs_start - t0) * 1000,
            (t_filter_done - t_bfs_start) * 1000,
            (t_dijkstra_done - t_filter_done) * 1000,
            (t_end - t_dijkstra_done) * 1000,
            (t_end - t0) * 1000,
            iterations,
            found_node,
            is_teleport_fallback,
        )

        return PathResult(
            found=True,
            total_cost=total_cost,
            steps=steps,
            segments=segments,
            transports_used=transports_used,
            transports_metadata=transports_metadata,
            walk_distance=walk_distance,
            iterations=iterations,
            matched_spawns=matched_spawns,
        )

    def find_nearest_bank_detailed(
        self,
        start: tuple[int, int, int],
        player_context: PlayerContext | None = None,
        use_teleports: bool = True,
        disabled_types: frozenset[TransportType] | None = None,
        ellipse_margin: float = 1.2,
        max_segment_iterations: int = 100000,
    ) -> DetailedPathResult:
        """Find nearest bank with tile-by-tile details."""
        start_time = time.perf_counter()

        graph_result = self.find_nearest_bank(
            start,
            player_context,
            use_teleports,
            disabled_types,
        )

        if not graph_result.found:
            return DetailedPathResult(
                found=False,
                graph_result=graph_result,
                elapsed_ms=(time.perf_counter() - start_time) * 1000,
            )

        return _build_detailed_from_graph_result(
            self, start, graph_result, start_time, ellipse_margin, max_segment_iterations
        )
