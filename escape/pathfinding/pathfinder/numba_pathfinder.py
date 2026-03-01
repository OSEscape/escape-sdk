"""Tile-level BFS pathfinder."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from escape.pathfinding.pathfinder.bfs import (
    _BYTES_PER_REGION,
    _bfs_find_any_target,
    _bfs_find_k_targets,
    _bfs_pathfind_bitpacked,
    _pack_point,
)
from escape.pathfinding.pathfinder.collision_grid import CollisionGrid, FastPathResult

if TYPE_CHECKING:
    from escape.pathfinding.pathfinder.split_flag_map import SplitFlagMap

# =============================================================================
# NumbaPathfinder Class
# =============================================================================


class NumbaPathfinder:
    """High-performance BFS pathfinder using Rust native extension."""

    __slots__ = (
        "_fwd_active_regions",
        "_fwd_parent",
        "_fwd_queue",
        "_fwd_region_allocated",
        "_fwd_regions",
        "_queue_size",
        "_rg",
        "grid",
    )

    def __init__(self, collision_grid: CollisionGrid, queue_size: int = 250000):
        """Create NumbaPathfinder from pre-processed collision data."""
        self.grid = collision_grid
        self._queue_size = queue_size
        self._rg = collision_grid.rg

        max_regions = int(self._rg[0]) * int(self._rg[1])

        # Pre-allocate search arrays
        self._fwd_regions = np.zeros(max_regions * _BYTES_PER_REGION, dtype=np.uint8)
        self._fwd_region_allocated = np.zeros(max_regions, dtype=np.bool_)
        self._fwd_active_regions = np.zeros(max_regions, dtype=np.int32)
        self._fwd_queue = np.empty(queue_size, dtype=np.int64)
        self._fwd_parent = np.empty(queue_size, dtype=np.int32)

        # Warm up native extension
        self._warmup()

    def _warmup(self):
        """Warm up JIT compilation for BFS."""
        # Use min_x/min_y from rg[4]/rg[5]
        dummy_start = _pack_point(int(self._rg[4]) + 10, int(self._rg[5]) + 10, 0)
        dummy_target = _pack_point(int(self._rg[4]) + 15, int(self._rg[5]) + 15, 0)
        _bfs_pathfind_bitpacked(
            dummy_start,
            dummy_target,
            self.grid.flags_data,
            self.grid.region_index,
            self._fwd_regions,
            self._fwd_region_allocated,
            self._fwd_active_regions,
            self._fwd_queue,
            self._fwd_parent,
            self._rg,
            100,
        )
        self._reset_visited()

    def _reset_visited(self):
        """Reset visited regions using fast numpy operations."""
        # Find allocated region indices with numpy (fast)
        allocated_indices = np.where(self._fwd_region_allocated)[0]

        # Reset only allocated regions
        for i in allocated_indices:
            start = i * _BYTES_PER_REGION
            end = start + _BYTES_PER_REGION
            self._fwd_regions[start:end] = 0

        # Clear allocation tracking
        self._fwd_region_allocated[allocated_indices] = False

    def find_path(
        self,
        start_x: int,
        start_y: int,
        start_z: int,
        target_x: int,
        target_y: int,
        target_z: int,
        max_iterations: int = 500000,
    ) -> FastPathResult:
        """Find path between two points using BFS."""
        import time

        start_packed = _pack_point(start_x, start_y, start_z)
        target_packed = _pack_point(target_x, target_y, target_z)

        start_time = time.perf_counter()

        self._reset_visited()

        path_array, iterations, found, _ = _bfs_pathfind_bitpacked(
            start_packed,
            target_packed,
            self.grid.flags_data,
            self.grid.region_index,
            self._fwd_regions,
            self._fwd_region_allocated,
            self._fwd_active_regions,
            self._fwd_queue,
            self._fwd_parent,
            self._rg,
            max_iterations,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return FastPathResult(
            path=[int(p) for p in path_array],
            found=found,
            nodes_checked=iterations,
            elapsed_ms=elapsed_ms,
        )

    def find_nearest_target(
        self,
        start_x: int,
        start_y: int,
        start_z: int,
        targets_sorted: np.ndarray,
        max_iterations: int = 100000,
    ) -> tuple[int, int, bool]:
        """Find nearest reachable target via BFS. Return (target_packed, distance, found)."""
        start_packed = _pack_point(start_x, start_y, start_z)

        # Reset visited tracking
        self._reset_visited()

        found_target, distance, _iterations, found = _bfs_find_any_target(
            start_packed,
            targets_sorted,
            self.grid.flags_data,
            self.grid.region_index,
            self._fwd_regions,
            self._fwd_region_allocated,
            self._fwd_active_regions,
            self._fwd_queue,
            self._rg,
            max_iterations,
        )

        return found_target, distance, found

    def find_k_nearest_targets(
        self,
        start_x: int,
        start_y: int,
        start_z: int,
        targets_sorted: np.ndarray,
        k: int = 5,
        max_iterations: int = 200000,
    ) -> tuple[np.ndarray, np.ndarray, int]:
        """Find up to k nearest reachable targets. Return (targets, distances, num_found)."""
        start_packed = _pack_point(start_x, start_y, start_z)

        # Reset visited tracking
        self._reset_visited()

        # Allocate output arrays
        out_targets = np.zeros(k, dtype=np.int64)
        out_distances = np.zeros(k, dtype=np.int32)

        num_found, _iterations = _bfs_find_k_targets(
            start_packed,
            targets_sorted,
            self.grid.flags_data,
            self.grid.region_index,
            self._fwd_regions,
            self._fwd_region_allocated,
            self._fwd_active_regions,
            self._fwd_queue,
            self._rg,
            max_iterations,
            k,
            out_targets,
            out_distances,
        )

        return out_targets[:num_found], out_distances[:num_found], num_found

    @classmethod
    def from_collision_data(
        cls, split_flag_map: SplitFlagMap, queue_size: int = 250000
    ) -> NumbaPathfinder:
        """Create NumbaPathfinder from a pre-loaded/modified SplitFlagMap."""
        grid = CollisionGrid(split_flag_map)
        return cls(grid, queue_size=queue_size)

    def memory_usage(self) -> dict:
        """Return memory usage breakdown in bytes."""
        fwd_regions = self._fwd_regions.nbytes
        fwd_tracking = self._fwd_region_allocated.nbytes + self._fwd_active_regions.nbytes
        fwd_queue = self._fwd_queue.nbytes + self._fwd_parent.nbytes
        collision = self.grid.flags_data.nbytes + self.grid.region_index.nbytes

        return {
            "visited_regions": fwd_regions,
            "region_tracking": fwd_tracking,
            "queues": fwd_queue,
            "collision_data": collision,
            "total": fwd_regions + fwd_tracking + fwd_queue + collision,
        }
