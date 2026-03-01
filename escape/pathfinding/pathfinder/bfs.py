"""BFS pathfinding primitives and algorithms via Rust native extension.

Uses region-indexed bitpacked collision data for memory efficiency.
Flag lookup: fd=flags_data (uint8[]), ri=region_index (int32[]),
rg=[region_cols, region_rows, min_region_x, min_region_y, min_x, min_y].
"""

from __future__ import annotations

from escape.pathfinding.pathfinder.flag_map import REGION_SIZE

# Bitpacked visited tracking constant (used by NumbaPathfinder for buffer allocation)
_BYTES_PER_REGION = (REGION_SIZE * REGION_SIZE) // 8

from escape.pathfinding._native import (
    bfs_find_any_target as _bfs_find_any_target_native,
    bfs_find_k_targets as _bfs_find_k_targets_native,
    bfs_pathfind as _bfs_pathfind_native,
)


def _pack_point(x, y, z):
    return (x & 0x7FFF) | ((y & 0x7FFF) << 15) | ((z & 0x3) << 30)


# Wrappers matching legacy signatures (state arrays passed but ignored)


def _bfs_pathfind_bitpacked(
    start_packed,
    target_packed,
    fd,
    ri,
    regions,
    region_allocated,
    active_regions,
    queue,
    parent,
    rg,
    max_iterations,
):
    path, iterations, found = _bfs_pathfind_native(
        start_packed, target_packed, fd, ri, rg, len(queue), max_iterations
    )
    return path, iterations, found, 0


def _bfs_find_any_target(
    start_packed,
    targets_sorted,
    fd,
    ri,
    regions,
    region_allocated,
    active_regions,
    queue,
    rg,
    max_iterations,
):
    return _bfs_find_any_target_native(
        start_packed, targets_sorted, fd, ri, rg, len(queue), max_iterations
    )


def _bfs_find_k_targets(
    start_packed,
    targets_sorted,
    fd,
    ri,
    regions,
    region_allocated,
    active_regions,
    queue,
    rg,
    max_iterations,
    max_targets,
    out_targets,
    out_distances,
):
    targets, distances, num_found, iterations = _bfs_find_k_targets_native(
        start_packed, targets_sorted, fd, ri, rg, len(queue), max_iterations, max_targets
    )
    out_targets[:num_found] = targets[:num_found]
    out_distances[:num_found] = distances[:num_found]
    return num_found, iterations
