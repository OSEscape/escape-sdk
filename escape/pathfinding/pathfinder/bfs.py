"""BFS pathfinding primitives and algorithms.

Prefers Rust native extension for zero cold-start latency; falls back to
Numba JIT if the native module is not available.

Uses region-indexed bitpacked collision data for memory efficiency.
Flag lookup: fd=flags_data (uint8[]), ri=region_index (int32[]),
rg=[region_cols, region_rows, min_region_x, min_region_y, min_x, min_y].
"""

from __future__ import annotations

import numpy as np

from escape.pathfinding.pathfinder.flag_map import REGION_SIZE

# Region bounds: rg[0]=region_cols, rg[1]=region_rows,
#                rg[2]=min_region_x, rg[3]=min_region_y,
#                rg[4]=min_x, rg[5]=min_y

# Bitpacked layout constants (must match collision_grid.py)
_BP_BYTES_PER_ROW = 8  # 64 columns / 8 bits
_BP_BYTES_PER_FLAG = _BP_BYTES_PER_ROW * REGION_SIZE  # 512
_BP_BYTES_PER_PLANE = _BP_BYTES_PER_FLAG * 2  # 1024

# Bitpacked visited tracking constants
_REGION_BITS = 6
_REGION_MASK = (1 << _REGION_BITS) - 1
_TILES_PER_REGION = REGION_SIZE * REGION_SIZE
_BYTES_PER_REGION = _TILES_PER_REGION // 8

try:
    from escape.pathfinding._native import (
        bfs_find_any_target as _bfs_find_any_target_native,
        bfs_find_k_targets as _bfs_find_k_targets_native,
        bfs_pathfind as _bfs_pathfind_native,
    )

    def _pack_point(x, y, z):
        return (x & 0x7FFF) | ((y & 0x7FFF) << 15) | ((z & 0x3) << 30)

    # Wrappers matching Numba signatures (state arrays passed but ignored)

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

except ImportError:
    from numba import njit

    # --- Flag Lookup ---

    @njit(cache=True)
    def _get_flag(fd, ri, x, y, z, flag_type, rg):
        """Core bitpacked flag lookup."""
        if z < 0 or z >= 4:
            return False
        rx_off = (x >> 6) - rg[2]
        ry_off = (y >> 6) - rg[3]
        if rx_off < 0 or rx_off >= rg[0] or ry_off < 0 or ry_off >= rg[1]:
            return False
        region_offset = ri[ry_off * rg[0] + rx_off]
        if region_offset < 0:
            return False
        byte_off = (
            region_offset
            + z * _BP_BYTES_PER_PLANE
            + flag_type * _BP_BYTES_PER_FLAG
            + (y & 63) * _BP_BYTES_PER_ROW
            + ((x & 63) >> 3)
        )
        return (fd[byte_off] >> (x & 7)) & 1 != 0

    # --- Movement Primitives ---

    @njit(cache=True)
    def _can_move_north(fd, ri, x, y, z, rg):
        return _get_flag(fd, ri, x, y, z, 0, rg)

    @njit(cache=True)
    def _can_move_east(fd, ri, x, y, z, rg):
        return _get_flag(fd, ri, x, y, z, 1, rg)

    @njit(cache=True)
    def _can_move_south(fd, ri, x, y, z, rg):
        return _can_move_north(fd, ri, x, y - 1, z, rg)

    @njit(cache=True)
    def _can_move_west(fd, ri, x, y, z, rg):
        return _can_move_east(fd, ri, x - 1, y, z, rg)

    # --- Coordinate Packing ---

    @njit(cache=True)
    def _pack_point(x, y, z):
        return (x & 0x7FFF) | ((y & 0x7FFF) << 15) | ((z & 0x3) << 30)

    @njit(cache=True)
    def _unpack_x(packed):
        return packed & 0x7FFF

    @njit(cache=True)
    def _unpack_y(packed):
        return (packed >> 15) & 0x7FFF

    @njit(cache=True)
    def _unpack_z(packed):
        return (packed >> 30) & 0x3

    # --- Bitpacked Visited Tracking ---
    # Each region: 64x64 tiles = 512 bytes (BFS never crosses planes)

    @njit(cache=True)
    def _mark_visited(packed, regions, region_allocated, active_regions, active_count, rg):
        """Mark packed position as visited."""
        x, y = _unpack_x(packed), _unpack_y(packed)

        rx = (x >> _REGION_BITS) - rg[2]
        ry = (y >> _REGION_BITS) - rg[3]
        if rx < 0 or rx >= rg[0] or ry < 0 or ry >= rg[1]:
            return False, active_count

        region_idx = ry * rg[0] + rx
        new_ac = active_count
        if not region_allocated[region_idx]:
            region_allocated[region_idx] = True
            active_regions[active_count] = region_idx
            new_ac = active_count + 1

        local_x, local_y = x & _REGION_MASK, y & _REGION_MASK
        bit_idx = local_y * REGION_SIZE + local_x
        byte_idx = bit_idx >> 3
        region_start = region_idx * _BYTES_PER_REGION
        mask = np.uint8(1 << (bit_idx & 7))

        if regions[region_start + byte_idx] & mask:
            return False, new_ac
        regions[region_start + byte_idx] |= mask
        return True, new_ac

    # --- Shared BFS Helpers ---

    @njit(cache=True)
    def _get_valid_neighbors(x, y, z, fd, ri, rg, out):
        """Get movement-valid neighbors. Writes packed positions to out, returns count."""
        count = 0
        can_n = _can_move_north(fd, ri, x, y, z, rg)
        can_s = _can_move_south(fd, ri, x, y, z, rg)
        can_e = _can_move_east(fd, ri, x, y, z, rg)
        can_w = _can_move_west(fd, ri, x, y, z, rg)

        if can_w:
            out[count] = _pack_point(x - 1, y, z)
            count += 1
        if can_e:
            out[count] = _pack_point(x + 1, y, z)
            count += 1
        if can_s:
            out[count] = _pack_point(x, y - 1, z)
            count += 1
        if can_n:
            out[count] = _pack_point(x, y + 1, z)
            count += 1
        if (
            can_s
            and can_w
            and _can_move_west(fd, ri, x, y - 1, z, rg)
            and _can_move_south(fd, ri, x - 1, y, z, rg)
        ):
            out[count] = _pack_point(x - 1, y - 1, z)
            count += 1
        if (
            can_s
            and can_e
            and _can_move_east(fd, ri, x, y - 1, z, rg)
            and _can_move_south(fd, ri, x + 1, y, z, rg)
        ):
            out[count] = _pack_point(x + 1, y - 1, z)
            count += 1
        if (
            can_n
            and can_w
            and _can_move_west(fd, ri, x, y + 1, z, rg)
            and _can_move_north(fd, ri, x - 1, y, z, rg)
        ):
            out[count] = _pack_point(x - 1, y + 1, z)
            count += 1
        if (
            can_n
            and can_e
            and _can_move_east(fd, ri, x, y + 1, z, rg)
            and _can_move_north(fd, ri, x + 1, y, z, rg)
        ):
            out[count] = _pack_point(x + 1, y + 1, z)
            count += 1
        return count

    # --- BFS 1: Point-to-Point Pathfinding ---

    @njit(cache=True)
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
        """BFS point-to-point pathfinding."""
        _, active_count = _mark_visited(
            start_packed, regions, region_allocated, active_regions, 0, rg
        )
        queue[0] = start_packed
        parent[0] = -1
        queue_head = 0
        queue_tail = 1
        iterations = 0
        found_idx = -1
        nbuf = np.empty(8, dtype=np.int64)

        while queue_head < queue_tail and iterations < max_iterations:
            iterations += 1
            current_idx = queue_head
            current = queue[queue_head]
            queue_head += 1

            if current == target_packed:
                found_idx = current_idx
                break

            x, y, z = _unpack_x(current), _unpack_y(current), _unpack_z(current)
            nc = _get_valid_neighbors(x, y, z, fd, ri, rg, nbuf)
            for ni in range(nc):
                nb = nbuf[ni]
                is_new, active_count = _mark_visited(
                    nb,
                    regions,
                    region_allocated,
                    active_regions,
                    active_count,
                    rg,
                )
                if is_new:
                    queue[queue_tail] = nb
                    parent[queue_tail] = current_idx
                    queue_tail += 1

        if found_idx >= 0:
            path_len = 0
            idx = found_idx
            while idx >= 0:
                path_len += 1
                idx = parent[idx]
            path = np.empty(path_len, dtype=np.int64)
            idx = found_idx
            for i in range(path_len - 1, -1, -1):
                path[i] = queue[idx]
                idx = parent[idx]
            return path, iterations, True, active_count

        return np.empty(0, dtype=np.int64), iterations, False, active_count

    # --- BFS 2: Find Nearest Target ---

    @njit(cache=True)
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
        """BFS to find nearest target from a sorted target array."""
        idx = np.searchsorted(targets_sorted, start_packed)
        if idx < len(targets_sorted) and targets_sorted[idx] == start_packed:
            return start_packed, 0, 0, True

        _, active_count = _mark_visited(
            start_packed, regions, region_allocated, active_regions, 0, rg
        )
        queue[0] = start_packed
        dist_arr = np.zeros(len(queue), dtype=np.int32)
        queue_head = 0
        queue_tail = 1
        iterations = 0
        nbuf = np.empty(8, dtype=np.int64)

        while queue_head < queue_tail and iterations < max_iterations:
            iterations += 1
            current = queue[queue_head]
            current_dist = dist_arr[queue_head]
            queue_head += 1

            x, y, z = _unpack_x(current), _unpack_y(current), _unpack_z(current)
            next_dist = current_dist + 1

            nc = _get_valid_neighbors(x, y, z, fd, ri, rg, nbuf)
            for ni in range(nc):
                nb = nbuf[ni]
                tidx = np.searchsorted(targets_sorted, nb)
                if tidx < len(targets_sorted) and targets_sorted[tidx] == nb:
                    return nb, next_dist, iterations, True

                is_new, active_count = _mark_visited(
                    nb,
                    regions,
                    region_allocated,
                    active_regions,
                    active_count,
                    rg,
                )
                if is_new:
                    queue[queue_tail] = nb
                    dist_arr[queue_tail] = next_dist
                    queue_tail += 1

        return 0, -1, iterations, False

    # --- BFS 3: Find K Nearest Targets ---

    @njit(cache=True)
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
        """BFS to find up to K nearest targets."""
        num_found = 0
        _, active_count = _mark_visited(
            start_packed, regions, region_allocated, active_regions, 0, rg
        )
        queue[0] = start_packed
        dist_arr = np.zeros(len(queue), dtype=np.int32)
        queue_head = 0
        queue_tail = 1
        iterations = 0
        nbuf = np.empty(8, dtype=np.int64)

        while queue_head < queue_tail and iterations < max_iterations and num_found < max_targets:
            iterations += 1
            current = queue[queue_head]
            current_dist = dist_arr[queue_head]
            queue_head += 1

            x, y, z = _unpack_x(current), _unpack_y(current), _unpack_z(current)
            next_dist = current_dist + 1

            nc = _get_valid_neighbors(x, y, z, fd, ri, rg, nbuf)
            for ni in range(nc):
                nb = nbuf[ni]
                is_new, active_count = _mark_visited(
                    nb,
                    regions,
                    region_allocated,
                    active_regions,
                    active_count,
                    rg,
                )
                if is_new:
                    if nb != start_packed:
                        tidx = np.searchsorted(targets_sorted, nb)
                        if tidx < len(targets_sorted) and targets_sorted[tidx] == nb:
                            out_targets[num_found] = nb
                            out_distances[num_found] = next_dist
                            num_found += 1
                            if num_found >= max_targets:
                                return num_found, iterations
                    queue[queue_tail] = nb
                    dist_arr[queue_tail] = next_dist
                    queue_tail += 1

        return num_found, iterations
