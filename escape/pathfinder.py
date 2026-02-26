import threading
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

import numpy as np

from escape._logger import logger
from escape._math import _combat_level
from escape.pathfinding.core.enums import TransportType
from escape.pathfinding.pathfinder.bfs import _get_valid_neighbors
from escape.point import Point

if TYPE_CHECKING:
    from escape.pathfinding.core.player_context import PlayerContext
    from escape.pathfinding.pathfinder.graph_pathfinder import GraphPathfinder
    from escape.pathfinding.pathfinder.transport_metadata import TransportMetadata


def _parse_transport_type(name: str) -> TransportType:
    """Parse a TransportType from its string name, defaulting to TRANSPORT."""
    try:
        return TransportType[name]
    except KeyError:
        return TransportType.TRANSPORT


@dataclass
class Transport:
    """A transport hop in a pathfinding result."""

    origin: Point
    destination: Point
    name: str
    transport_type: TransportType = TransportType.TRANSPORT
    metadata: list[TransportMetadata] | None = None


@dataclass
class Path:
    """Result of a pathfinding query."""

    found: bool
    tile_path: list[Point] = field(default_factory=list)
    transports: list[Transport] = field(default_factory=list)
    cost: int = 0
    elapsed_ms: float = 0.0

    @cached_property
    def _packed(self) -> np.ndarray:
        if not self.tile_path:
            return np.array([], dtype=np.uint32)
        return np.array([p.packed for p in self.tile_path], dtype=np.uint32)

    @property
    def world_x(self) -> np.ndarray:
        """World X coordinates of each tile in the path."""
        return (self._packed & 0x7FFF).astype(np.int32)

    @property
    def world_y(self) -> np.ndarray:
        """World Y coordinates of each tile in the path."""
        return ((self._packed >> 15) & 0x7FFF).astype(np.int32)

    def length(self) -> int:
        """Return the number of tiles in the path."""
        return len(self.tile_path)

    def is_empty(self) -> bool:
        """Check whether the path has no tiles."""
        return len(self.tile_path) == 0


@dataclass(frozen=True)
class PathfinderConfig:
    """Configuration for pathfinding queries."""

    disabled_types: frozenset[TransportType] = field(
        default_factory=lambda: frozenset(
            {
                TransportType.CANOE,
                TransportType.HOT_AIR_BALLOON,
                TransportType.SEASONAL_TRANSPORTS,
                TransportType.TELEPORTATION_BOX,
                TransportType.TELEPORTATION_PORTAL_POH,
                TransportType.WILDERNESS_OBELISK,
            }
        )
    )
    use_teleports: bool = True
    use_bank_items: bool = False
    max_iterations: int = 1000000

    @classmethod
    def with_disabled(cls, *types: TransportType) -> PathfinderConfig:
        """Create a config with the given transport types disabled."""
        return cls(disabled_types=frozenset(types))


WALK_ONLY = PathfinderConfig(use_teleports=False)

_graph_pf: GraphPathfinder | None = None
_load_lock = threading.Lock()


def _get_graph_pathfinder() -> GraphPathfinder:
    global _graph_pf
    if _graph_pf is not None:
        return _graph_pf

    with _load_lock:
        if _graph_pf is not None:
            return _graph_pf

        from escape._cache_manager import get_game_data_dir
        from escape.pathfinding.pathfinder.graph_pathfinder import GraphPathfinder

        graph_dir = get_game_data_dir() / "graph"
        logger.info("Loading pathfinding graph from %s...", graph_dir)
        _graph_pf = GraphPathfinder.from_directory(graph_dir)
        logger.info("Pathfinding graph loaded.")
        return _graph_pf


def _normalize_point(point: Point | tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(point, Point):
        return (point.x, point.y, point.plane)
    return point


def _metadata_from_edge_transport(
    edge_t: object | None,
    from_node_id: int,
    to_node_id: int,
) -> list[TransportMetadata] | None:
    """Build a single-element metadata list from an edge Transport object."""
    from escape.pathfinding.transport.transport import Transport as GraphTransport

    if not isinstance(edge_t, GraphTransport):
        return None

    origin_coords = edge_t.get_origin_coords()
    dest_coords = edge_t.get_destination_coords()
    dest_x = dest_coords[0] if dest_coords else 0
    dest_y = dest_coords[1] if dest_coords else 0
    dest_plane = dest_coords[2] if dest_coords else 0

    item_ids: list[int] = []
    if edge_t.item_requirements:
        for item_list in edge_t.item_requirements.items:
            if item_list:
                item_ids.extend(item_list)

    from escape.pathfinding.pathfinder.transport_metadata import TransportMetadata as TMeta

    return [
        TMeta(
            node_id=from_node_id,
            transport_id=from_node_id,
            name=edge_t.display_info or edge_t.object_info or edge_t.transport_type.name,
            transport_type=edge_t.transport_type.name,
            x=dest_x,
            y=dest_y,
            plane=dest_plane,
            origin_x=origin_coords[0] if origin_coords else None,
            origin_y=origin_coords[1] if origin_coords else None,
            origin_plane=origin_coords[2] if origin_coords else None,
            is_spawn_point=False,
            activation_cost=(edge_t.duration * 2) + 4,
            duration_ticks=edge_t.duration,
            skill_requirements=dict(edge_t.skill_levels),
            quest_requirements=list(edge_t.quests),
            item_requirements=item_ids,
            varbit_requirements=[
                (v.varbit_id, v.value, v.check_type.value) for v in edge_t.varbits
            ],
            varplayer_requirements=[
                (v.varplayer_id, v.value, v.check_type.value) for v in edge_t.varplayers
            ],
            max_wilderness_level=edge_t.max_wilderness_level,
            display_info=edge_t.display_info or "",
            action=edge_t.object_info or "",
            is_consumable=edge_t.is_consumable,
        )
    ]


def _detailed_to_result(
    pf: GraphPathfinder,
    detailed: object,
) -> Path:
    from escape.pathfinding.pathfinder.path_types import DetailedPathResult

    assert isinstance(detailed, DetailedPathResult)

    if not detailed.found:
        return Path(found=False, elapsed_ms=detailed.elapsed_ms)

    tile_path = [Point(x, y, plane) for x, y, plane in detailed.tile_path]

    matched = detailed.matched_spawns
    transports = []
    for origin, dest, name, node_id, from_node_id in detailed.transport_hops:
        t_type = TransportType.TRANSPORT
        if from_node_id >= 0:
            # Edge transport: look up the actual edge Transport object
            edge_t = pf.get_edge_transport(from_node_id, node_id)
            if edge_t:
                t_type = edge_t.transport_type
                edge_name = edge_t.display_info or edge_t.object_info
                if edge_name:
                    name = edge_name
            # Fairy rings: node name is the destination code to dial, not the origin
            if t_type == TransportType.FAIRY_RING:
                dest_name = pf._get_transport_name(node_id)
                if dest_name:
                    name = dest_name
            metadata = _metadata_from_edge_transport(edge_t, from_node_id, node_id)
            # Fall back to node metadata DB when no edge Transport object exists
            # (e.g. fairy rings, spirit trees — edges without per-edge requirements)
            if metadata is None:
                metadata = pf.get_transport_metadata(from_node_id)
            if t_type == TransportType.TRANSPORT and metadata:
                t_type = _parse_transport_type(metadata[0].transport_type)
        else:
            # Spawn transport: metadata on destination node, filter by matched transport
            matched_transport = matched.get(node_id)
            metadata = pf.get_transport_metadata(node_id)
            if matched_transport:
                t_type = matched_transport.transport_type
                if matched_transport.display_info:
                    name = matched_transport.display_info
                # Pick the matching metadata entry by index (same order as spawn_transports)
                if metadata and node_id in pf.spawn_transports:
                    spawn_list = pf.spawn_transports[node_id]
                    for i, t in enumerate(spawn_list):
                        if t == matched_transport and i < len(metadata):
                            metadata = [metadata[i]]
                            break
            elif metadata:
                t_type = _parse_transport_type(metadata[0].transport_type)
        transports.append(
            Transport(
                origin=Point(*origin),
                destination=Point(*dest),
                name=name,
                transport_type=t_type,
                metadata=metadata,
            )
        )

    return Path(
        found=True,
        tile_path=tile_path,
        transports=transports,
        cost=detailed.total_cost,
        elapsed_ms=detailed.elapsed_ms,
    )


def _find_nearest_walkable(
    pos: tuple[int, int, int],
    fd: np.ndarray,
    ri: np.ndarray,
    rg: np.ndarray,
    max_radius: int = 5,
) -> tuple[int, int, int] | None:
    """Find the nearest tile with >0 valid neighbors within Chebyshev radius."""
    x, y, z = pos
    nbuf = np.empty(8, dtype=np.int64)
    for r in range(1, max_radius + 1):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                if _get_valid_neighbors(x + dx, y + dy, z, fd, ri, rg, nbuf) > 0:
                    return (x + dx, y + dy, z)
    return None


def _nudge_blocked_goal(
    goal: tuple[int, int, int],
    fd: np.ndarray,
    ri: np.ndarray,
    rg: np.ndarray,
) -> tuple[int, int, int]:
    """If goal tile is blocked in static collision, redirect to adjacent walkable tile."""
    x, y, z = goal
    nbuf = np.empty(8, dtype=np.int64)
    if _get_valid_neighbors(x, y, z, fd, ri, rg, nbuf) > 0:
        return goal

    from escape._resources.objects import find_object_at

    obj = find_object_at(x, y, z)
    if obj is not None:
        tiles_set = set(obj.tiles)
        min_x = min(t[0] for t in tiles_set)
        max_x = max(t[0] for t in tiles_set)
        min_y = min(t[1] for t in tiles_set)
        max_y = max(t[1] for t in tiles_set)
        best: tuple[int, int, int] | None = None
        best_dist = 999
        for ax in range(min_x - 1, max_x + 2):
            for ay in range(min_y - 1, max_y + 2):
                if (ax, ay, z) in tiles_set:
                    continue
                if _get_valid_neighbors(ax, ay, z, fd, ri, rg, nbuf) > 0:
                    dist = max(abs(ax - x), abs(ay - y))
                    if dist < best_dist:
                        best_dist = dist
                        best = (ax, ay, z)
        if best is not None:
            logger.debug("nudge: goal ({},{},{}) → ({},{},{}) via object '{}'",
                         x, y, z, best[0], best[1], best[2], obj.name)
            return best

    alt = _find_nearest_walkable(goal, fd, ri, rg)
    if alt is not None:
        logger.debug("nudge: goal ({},{},{}) → ({},{},{}) via spiral", x, y, z, *alt)
        return alt
    return goal


class Pathfinder:
    """Graph-based pathfinder for world navigation."""

    def __init__(self):
        from escape._services import Services

        self._cache = Services.get().cache

    def _get_start(self) -> tuple[int, int, int]:
        pos = self._cache.world_position
        if pos is None:
            raise RuntimeError("Player position not available (not logged in?)")
        return pos

    def _build_context(self) -> PlayerContext:
        from escape.pathfinding.core.player_context import PlayerContext

        pos = self._cache.world_position or (0, 0, 0)

        skills_data = self._cache.skills
        skill_levels = {name.upper(): s.level for name, s in skills_data.items()}
        total_level = sum(s.level for s in skills_data.values()) if skills_data else 0

        from escape._resources import varps
        from escape.constants import VarPlayerID

        quest_points = varps.get_varp_value(VarPlayerID.QP) or 0

        inventory = self._cache.inventory.quantity_by_id
        equipment = self._cache.equipment.quantity_by_id
        bank_container = self._cache.bank
        bank = bank_container.quantity_by_id if bank_container.items else None

        from escape.runepouch import bank_rune_pouch, inventory_rune_pouch

        rune_pouch = inventory_rune_pouch(inventory)
        if not rune_pouch:
            bank_pouch = bank_rune_pouch(bank)
            if bank_pouch:
                bank = dict(bank) if bank else {}
                for item_id, qty in bank_pouch.items():
                    bank[item_id] = bank.get(item_id, 0) + qty

        # TODO: member

        ctx = PlayerContext(
            position=pos,
            quest_points=quest_points,
            inventory=inventory,
            equipment=equipment,
            bank=bank,
            rune_pouch=rune_pouch,
        )
        if skill_levels:
            ctx.skill_levels = skill_levels
            ctx.total_level = total_level
            ctx.combat_level = _combat_level(
                attack=skill_levels.get("ATTACK", 1),
                strength=skill_levels.get("STRENGTH", 1),
                defence=skill_levels.get("DEFENCE", 1),
                hitpoints=skill_levels.get("HITPOINTS", 1),
                prayer=skill_levels.get("PRAYER", 1),
                ranged=skill_levels.get("RANGED", 1),
                magic=skill_levels.get("MAGIC", 1),
            )
        return ctx

    def find_path(
        self,
        goal: Point | tuple[int, int, int],
        config: PathfinderConfig | None = None,
        start: Point | tuple[int, int, int] | None = None,
    ) -> Path:
        """Find a detailed path to the goal with transport metadata."""
        pf = _get_graph_pathfinder()
        start_tuple = _normalize_point(start) if start is not None else self._get_start()
        goal_tuple = _normalize_point(goal)

        # Nudge start/goal if blocked in static collision
        np_pf = pf.numba_pathfinder
        fd, ri, rg = np_pf.grid.flags_data, np_pf.grid.region_index, np_pf._rg
        nbuf = np.empty(8, dtype=np.int64)
        if _get_valid_neighbors(start_tuple[0], start_tuple[1], start_tuple[2], fd, ri, rg, nbuf) == 0:
            alt = _find_nearest_walkable(start_tuple, fd, ri, rg)
            if alt is not None:
                start_tuple = alt
        goal_tuple = _nudge_blocked_goal(goal_tuple, fd, ri, rg)

        if config is None:
            config = PathfinderConfig()

        context = self._build_context()

        detailed = pf.find_path_detailed(
            start_tuple,
            goal_tuple,
            player_context=context,
            use_teleports=config.use_teleports,
            use_bank_items=config.use_bank_items,
            disabled_types=config.disabled_types or None,
            max_segment_iterations=config.max_iterations,
        )
        return _detailed_to_result(pf, detailed)

    def find_walk_path(
        self,
        goal: Point | tuple[int, int, int],
        config: PathfinderConfig | None = None,
        start: Point | tuple[int, int, int] | None = None,
    ) -> Path:
        """Find a walk-only path to the goal without teleports."""
        if config is None:
            walk_config = WALK_ONLY
        else:
            walk_config = PathfinderConfig(
                disabled_types=config.disabled_types,
                use_teleports=False,
                max_iterations=config.max_iterations,
            )
        return self.find_path(goal, config=walk_config, start=start)

    def find_nearest_bank(
        self,
        config: PathfinderConfig | None = None,
        start: Point | tuple[int, int, int] | None = None,
    ) -> Path:
        """Find a detailed path to the nearest bank."""
        pf = _get_graph_pathfinder()
        start_tuple = _normalize_point(start) if start is not None else self._get_start()

        if config is None:
            config = PathfinderConfig()

        context = self._build_context()

        detailed = pf.find_nearest_bank_detailed(
            start_tuple,
            player_context=context,
            use_teleports=config.use_teleports,
            disabled_types=config.disabled_types or None,
            max_segment_iterations=config.max_iterations,
        )
        return _detailed_to_result(pf, detailed)

    def find_static_path(
        self,
        start: Point | tuple[int, int, int],
        goal: Point | tuple[int, int, int],
    ) -> list[tuple[int, int, int]]:
        """BFS on static collision data. Returns list of (x, y, plane) world tiles."""
        from escape.pathfinding.core.world_point import unpack_world_point

        pf = _get_graph_pathfinder()
        s = _normalize_point(start)
        g = _normalize_point(goal)
        np_pf = pf.numba_pathfinder
        fd, ri, rg = np_pf.grid.flags_data, np_pf.grid.region_index, np_pf._rg
        nbuf = np.empty(8, dtype=np.int64)

        # Nudge goal if blocked
        g = _nudge_blocked_goal(g, fd, ri, rg)

        result = np_pf.find_path(s[0], s[1], s[2], g[0], g[1], g[2])
        if result.found:
            return [unpack_world_point(p) for p in result.path]

        # Check if start is blocked (0 valid neighbors on static collision)
        if _get_valid_neighbors(s[0], s[1], s[2], fd, ri, rg, nbuf) == 0:
            alt = _find_nearest_walkable(s, fd, ri, rg)
            if alt is not None:
                result = np_pf.find_path(alt[0], alt[1], alt[2], g[0], g[1], g[2])
                if result.found:
                    path = [unpack_world_point(p) for p in result.path]
                    return [s, *path]
        return []

    def can_reach(
        self,
        dest_x: int,
        dest_y: int,
        dest_plane: int = 0,
    ) -> bool:
        """Check whether a destination is reachable."""
        result = self.find_path((dest_x, dest_y, dest_plane))
        return result.found


__all__ = [
    "WALK_ONLY",
    "Path",
    "Pathfinder",
    "PathfinderConfig",
    "Transport",
    "TransportType",
]
