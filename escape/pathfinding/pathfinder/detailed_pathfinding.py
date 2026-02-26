"""Detailed tile-by-tile pathfinding using hybrid graph + BFS approach."""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

from escape.pathfinding.core.world_point import unpack_world_plane, unpack_world_x, unpack_world_y
from escape.pathfinding.pathfinder.path_types import DetailedPathResult, WalkSegment

if TYPE_CHECKING:
    from escape.pathfinding.core.enums import TransportType
    from escape.pathfinding.core.player_context import PlayerContext
    from escape.pathfinding.pathfinder.graph_pathfinder import GraphPathfinder
    from escape.pathfinding.pathfinder.path_types import PathResult


def _build_detailed_from_graph_result(
    pf: GraphPathfinder,
    start: tuple[int, int, int],
    graph_result: PathResult,
    start_time: float,
    ellipse_margin: float = 1.2,
    max_segment_iterations: int = 100000,
) -> DetailedPathResult:
    """Shared core: run tile-by-tile BFS on walk segments from a pre-computed PathResult.

    Derives goal from the last step in graph_result.
    Used by both find_path_detailed and find_nearest_bank_detailed.
    """
    last_step = graph_result.steps[-1]
    goal = (last_step.x, last_step.y, last_step.plane)

    # Extract critical waypoints (transport locations + goal)
    walk_segments, transport_hops = _extract_walk_segments(start, goal, graph_result)

    # Compute tile-by-tile path for each walk segment
    full_tile_path: list[tuple[int, int, int]] = []
    total_nodes_explored = 0
    segments_computed = 0

    for segment in walk_segments:
        # Compute ellipse bound
        ellipse_bound = max(
            segment.graph_distance * ellipse_margin,
            segment.euclidean_distance * 1.5,  # Minimum bound
        )

        # Use NumbaPathfinder for the actual tile search
        # The ellipse bound is used to limit max_iterations proportionally
        estimated_max_nodes = int(ellipse_bound * ellipse_bound * 0.5)  # Rough area estimate
        iterations = min(max_segment_iterations, max(10000, estimated_max_nodes))

        result = pf.numba_pathfinder.find_path(
            segment.start[0],
            segment.start[1],
            segment.start[2],
            segment.end[0],
            segment.end[1],
            segment.end[2],
            max_iterations=iterations,
        )

        total_nodes_explored += result.nodes_checked
        segments_computed += 1

        if not result.found:
            # Segment failed - try with higher iteration limit
            result = pf.numba_pathfinder.find_path(
                segment.start[0],
                segment.start[1],
                segment.start[2],
                segment.end[0],
                segment.end[1],
                segment.end[2],
                max_iterations=max_segment_iterations * 2,
            )
            total_nodes_explored += result.nodes_checked

            if not result.found:
                # Still failed - return partial result
                return DetailedPathResult(
                    found=False,
                    tile_path=full_tile_path,
                    transport_hops=transport_hops,
                    graph_result=graph_result,
                    segments_computed=segments_computed,
                    total_nodes_explored=total_nodes_explored,
                    elapsed_ms=(time.perf_counter() - start_time) * 1000,
                )

        # Convert packed path to tile coordinates
        segment_tiles = _unpack_path(result.path)

        # Append to full path (avoid duplicating endpoints)
        # Skip first tile if it matches last tile of previous segment
        if full_tile_path and segment_tiles and segment_tiles[0] == full_tile_path[-1]:
            segment_tiles = segment_tiles[1:]
        full_tile_path.extend(segment_tiles)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return DetailedPathResult(
        found=True,
        total_cost=graph_result.total_cost,
        tile_path=full_tile_path,
        transport_hops=transport_hops,
        graph_result=graph_result,
        matched_spawns=graph_result.matched_spawns,
        segments_computed=segments_computed,
        total_nodes_explored=total_nodes_explored,
        elapsed_ms=elapsed_ms,
    )


def find_path_detailed(
    pf: GraphPathfinder,
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
    start_time = time.perf_counter()

    graph_result = pf.find_path(
        start,
        goal,
        player_context,
        use_teleports,
        use_bank_items=use_bank_items,
        disabled_types=disabled_types,
    )

    if not graph_result.found:
        return DetailedPathResult(
            found=False,
            graph_result=graph_result,
            elapsed_ms=(time.perf_counter() - start_time) * 1000,
        )

    return _build_detailed_from_graph_result(
        pf, start, graph_result, start_time, ellipse_margin, max_segment_iterations
    )


def _extract_walk_segments(
    start: tuple[int, int, int],
    goal: tuple[int, int, int],
    graph_result: PathResult,
) -> tuple[
    list[WalkSegment],
    list[tuple[tuple[int, int, int], tuple[int, int, int], str, int, int]],
]:
    """Extract walk segments and transport hops from graph result."""
    walk_segments: list[WalkSegment] = []
    transport_hops: list[tuple[tuple[int, int, int], tuple[int, int, int], str, int, int]] = []

    steps = graph_result.steps
    if len(steps) < 2:
        return walk_segments, transport_hops

    # Identify critical waypoints:
    # - 'start' and 'goal' are always critical
    # - 'teleport' is critical (destination, no origin needed - can teleport from anywhere)
    # - 'transport' is critical (destination)
    # - Step BEFORE 'transport' is critical (origin - need to walk there)
    is_critical = [False] * len(steps)
    is_transport_origin = [False] * len(steps)

    for i, step in enumerate(steps):
        if step.step_type in ("start", "goal", "teleport", "transport", "bank"):
            is_critical[i] = True

        # Mark step before 'transport' as critical (transport origin)
        if step.step_type == "transport" and i > 0:
            is_critical[i - 1] = True
            is_transport_origin[i - 1] = True

    # Build list of critical waypoints with their roles
    critical_points: list[tuple[tuple[int, int, int], bool, bool, str | None, int, int]] = []

    for i, step in enumerate(steps):
        if is_critical[i]:
            pos = (step.x, step.y, step.plane)
            is_origin = is_transport_origin[i]
            is_dest = step.step_type in ("transport", "teleport")
            name = "Bank" if step.step_type == "bank" else step.transport_name
            critical_points.append((pos, is_origin, is_dest, name, step.node_id, step.from_node_id))

    # Process critical points to extract walk segments and transport hops
    current_pos = critical_points[0][0]  # Start position

    i = 1
    while i < len(critical_points):
        pos, is_origin, is_dest, name, node_id, from_node_id = critical_points[i]

        if is_dest:
            # This is a transport/teleport destination
            transport_hops.append((current_pos, pos, name or "Transport", node_id, from_node_id))
            current_pos = pos
        elif is_origin:
            # This is a transport origin - we need to walk here
            if current_pos != pos:
                walk_segments.append(_make_walk_segment(current_pos, pos))
            current_pos = pos
        else:
            # Walk to this point (goal or bank)
            if current_pos != pos:
                walk_segments.append(_make_walk_segment(current_pos, pos))
            if name == "Bank":
                transport_hops.append((pos, pos, "Bank", node_id, from_node_id))
            current_pos = pos

        i += 1

    return walk_segments, transport_hops


def _make_walk_segment(
    current_pos: tuple[int, int, int], target_pos: tuple[int, int, int]
) -> WalkSegment:
    """Create a WalkSegment between two positions."""
    euclidean = math.sqrt(
        (target_pos[0] - current_pos[0]) ** 2 + (target_pos[1] - current_pos[1]) ** 2
    )
    graph_dist = int(euclidean * 1.4)
    return WalkSegment(
        start=current_pos,
        end=target_pos,
        graph_distance=max(graph_dist, int(euclidean)),
        euclidean_distance=euclidean,
    )


def _unpack_path(packed_path: list[int]) -> list[tuple[int, int, int]]:
    """Convert packed path coordinates to (x, y, plane) tuples."""
    tiles = []
    for packed in packed_path:
        x = unpack_world_x(packed)
        y = unpack_world_y(packed)
        plane = unpack_world_plane(packed)
        tiles.append((x, y, plane))
    return tiles
