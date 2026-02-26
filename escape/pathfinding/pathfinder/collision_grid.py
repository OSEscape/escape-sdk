"""Region-indexed bitpacked collision data for fast Numba access.

Instead of dense (4, height, width) bool arrays (~656MB), stores collision flags
as bitpacked regions (~8MB). Each 64x64 region is 4096 bytes:
4 planes x 2 flag types x 64 rows x 8 bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from escape.pathfinding.pathfinder.flag_map import REGION_SIZE

if TYPE_CHECKING:
    from escape.pathfinding.pathfinder.split_flag_map import SplitFlagMap

# Bitpacking layout constants
_BYTES_PER_ROW = 8  # 64 columns / 8 bits
_BYTES_PER_FLAG = _BYTES_PER_ROW * REGION_SIZE  # 512: one flag type, one plane
_BYTES_PER_PLANE = _BYTES_PER_FLAG * 2  # 1024: both flag types, one plane
BYTES_PER_REGION = _BYTES_PER_PLANE * 4  # 4096: all planes

FLAG_TYPE_NORTH = 0
FLAG_TYPE_EAST = 1


@dataclass
class FastPathResult:
    """Result from fast pathfinder."""

    path: list[int]
    found: bool
    nodes_checked: int
    elapsed_ms: float


class CollisionGrid:
    """Region-indexed bitpacked collision data for fast Numba access.

    Data is stored as two numpy arrays that Numba can index directly:
    - flags_data (uint8): concatenated bitpacked regions
    - region_index (int32): maps region slot -> byte offset in flags_data (-1 if empty)
    - rg (int32[6]): [region_cols, region_rows, min_region_x, min_region_y, min_x, min_y]
    """

    __slots__ = ("flags_data", "region_index", "rg")

    def __init__(self, split_flag_map: SplitFlagMap):
        """Create CollisionGrid from SplitFlagMap."""
        extents = split_flag_map.region_extents

        min_region_x = extents.min_x
        min_region_y = extents.min_y
        region_cols = extents.max_x - min_region_x + 1
        region_rows = extents.max_y - min_region_y + 1

        # Build region index and count populated regions
        num_slots = region_cols * region_rows
        self.region_index = np.full(num_slots, -1, dtype=np.int32)

        # First pass: count populated regions
        num_populated = 0
        for region_y in range(extents.min_y, extents.max_y + 1):
            for region_x in range(extents.min_x, extents.max_x + 1):
                idx = split_flag_map._get_index(region_x, region_y)
                if idx < 0 or idx >= len(split_flag_map._region_maps):
                    continue
                if split_flag_map._region_maps[idx] is None:
                    continue
                num_populated += 1

        # Allocate flags_data
        self.flags_data = np.zeros(num_populated * BYTES_PER_REGION, dtype=np.uint8)

        # Second pass: bitpack each populated region
        region_offset = 0
        for region_y in range(extents.min_y, extents.max_y + 1):
            for region_x in range(extents.min_x, extents.max_x + 1):
                idx = split_flag_map._get_index(region_x, region_y)
                if idx < 0 or idx >= len(split_flag_map._region_maps):
                    continue

                region_map = split_flag_map._region_maps[idx]
                if region_map is None:
                    continue

                # Store offset in region_index
                slot = (region_y - min_region_y) * region_cols + (region_x - min_region_x)
                self.region_index[slot] = region_offset

                # Bitpack this region's flags
                self._pack_region(region_map, region_offset)
                region_offset += BYTES_PER_REGION

        # Build metadata array
        self.rg = np.array(
            [
                region_cols,
                region_rows,
                min_region_x,
                min_region_y,
                min_region_x * REGION_SIZE,  # min_x in world coords
                min_region_y * REGION_SIZE,  # min_y in world coords
            ],
            dtype=np.int32,
        )

    def _pack_region(self, region_map, base_offset: int) -> None:
        """Bitpack a single region's flags into flags_data at base_offset."""
        flags = region_map._flags
        plane_count = min(4, region_map.plane_count)

        for plane in range(plane_count):
            plane_start = plane * REGION_SIZE * REGION_SIZE * 2
            plane_end = plane_start + REGION_SIZE * REGION_SIZE * 2

            if plane_end > len(flags):
                continue

            # Reshape to [y, x, flag_type]
            plane_flags = flags[plane_start:plane_end].reshape(REGION_SIZE, REGION_SIZE, 2)

            for flag_type in range(2):
                flag_data = plane_flags[:, :, flag_type]  # shape (64, 64), bool
                for row in range(REGION_SIZE):
                    byte_offset = (
                        base_offset
                        + plane * _BYTES_PER_PLANE
                        + flag_type * _BYTES_PER_FLAG
                        + row * _BYTES_PER_ROW
                    )
                    # Pack 64 bools into 8 bytes
                    row_data = flag_data[row]  # 64 bools
                    self.flags_data[byte_offset : byte_offset + _BYTES_PER_ROW] = np.packbits(
                        row_data, bitorder="little"
                    )

    def get_flag(self, x: int, y: int, z: int, flag_type: int) -> bool:
        """Look up a single flag at world coordinates."""
        if z < 0 or z >= 4:
            return False
        rx_off = (x >> 6) - self.rg[2]
        ry_off = (y >> 6) - self.rg[3]
        if rx_off < 0 or rx_off >= self.rg[0] or ry_off < 0 or ry_off >= self.rg[1]:
            return False
        region_offset = self.region_index[ry_off * self.rg[0] + rx_off]
        if region_offset < 0:
            return False
        local_x = x & 63
        local_y = y & 63
        byte_off = (
            region_offset
            + z * _BYTES_PER_PLANE
            + flag_type * _BYTES_PER_FLAG
            + local_y * _BYTES_PER_ROW
            + (local_x >> 3)
        )
        return bool((self.flags_data[byte_off] >> (local_x & 7)) & 1)

    def get_north(self, x: int, y: int, z: int) -> bool:
        """Check north movement flag at world coordinates."""
        return self.get_flag(x, y, z, FLAG_TYPE_NORTH)

    def get_east(self, x: int, y: int, z: int) -> bool:
        """Check east movement flag at world coordinates."""
        return self.get_flag(x, y, z, FLAG_TYPE_EAST)
