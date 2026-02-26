"""Split flag map for storing collision flags across multiple regions."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import numpy as np

from escape.pathfinding.pathfinder.flag_map import (
    FLAG_COUNT,
    FLAG_EAST,
    FLAG_NORTH,
    REGION_SIZE,
    FlagMap,
    RegionExtent,
    pack_region_position,
    unpack_region_x,
    unpack_region_y,
)

if TYPE_CHECKING:
    from pathlib import Path

# =============================================================================
# SplitFlagMap - All Regions
# =============================================================================


class SplitFlagMap:
    """Collection of FlagMaps for the entire OSRS world."""

    __slots__ = (
        "_cached_region",
        "_cached_region_x",
        "_cached_region_y",
        "_region_maps",
        "_region_plane_counts",
        "_width_inclusive",
        "region_extents",
    )

    def __init__(self, compressed_regions: dict[int, bytes], region_extents: RegionExtent):
        """Create a SplitFlagMap from compressed region data."""
        self.region_extents = region_extents
        self._width_inclusive = region_extents.width + 1
        height_inclusive = region_extents.height + 1

        # Create arrays for region maps
        total_regions = self._width_inclusive * height_inclusive
        self._region_maps: list[FlagMap | None] = [None] * total_regions
        self._region_plane_counts = np.zeros(total_regions, dtype=np.uint8)

        # Cache for last-accessed region (hot path optimization)
        self._cached_region: FlagMap | None = None
        self._cached_region_x: int = -1
        self._cached_region_y: int = -1

        # Load each region
        for packed_pos, data in compressed_regions.items():
            region_x = unpack_region_x(packed_pos)
            region_y = unpack_region_y(packed_pos)

            idx = self._get_index(region_x, region_y)
            if 0 <= idx < total_regions:
                flag_map = FlagMap(
                    min_x=region_x * REGION_SIZE, min_y=region_y * REGION_SIZE, data=data
                )
                self._region_maps[idx] = flag_map
                self._region_plane_counts[idx] = flag_map.plane_count

    def get(self, x: int, y: int, z: int, flag: int) -> bool:
        """Get a flag value at world coordinates."""
        region_x = x >> 6  # x // 64, faster with bit shift
        region_y = y >> 6  # y // 64

        # Check cache first (hot path - sequential tile accesses are usually in same region)
        if region_x == self._cached_region_x and region_y == self._cached_region_y:
            region_map = self._cached_region
            if region_map is None:
                return False
        else:
            idx = (region_x - self.region_extents.min_x) + (
                region_y - self.region_extents.min_y
            ) * self._width_inclusive
            if idx < 0 or idx >= len(self._region_maps):
                return False

            region_map = self._region_maps[idx]
            if region_map is None:
                return False

            # Update cache
            self._cached_region = region_map
            self._cached_region_x = region_x
            self._cached_region_y = region_y

        # Inline FlagMap.get() for performance
        # Bounds check
        local_x = x - region_map.min_x
        local_y = y - region_map.min_y
        if (
            local_x < 0
            or local_x >= REGION_SIZE
            or local_y < 0
            or local_y >= REGION_SIZE
            or z < 0
            or z >= region_map.plane_count
            or flag < 0
            or flag >= FLAG_COUNT
        ):
            return False

        idx = (z * REGION_SIZE * REGION_SIZE + local_y * REGION_SIZE + local_x) * FLAG_COUNT + flag
        return bool(region_map._flags[idx])

    def get_north(self, x: int, y: int, z: int) -> bool:
        """Check if tile can be traversed to the north."""
        return self.get(x, y, z, FLAG_NORTH)

    def get_east(self, x: int, y: int, z: int) -> bool:
        """Check if tile can be traversed to the east."""
        return self.get(x, y, z, FLAG_EAST)

    def get_plane_count(self, region_x: int, region_y: int) -> int:
        """Get plane count for a region."""
        idx = self._get_index(region_x, region_y)
        if idx < 0 or idx >= len(self._region_plane_counts):
            return 0
        return int(self._region_plane_counts[idx])

    def _get_index(self, region_x: int, region_y: int) -> int:
        """Get array index for a region."""
        return (region_x - self.region_extents.min_x) + (
            region_y - self.region_extents.min_y
        ) * self._width_inclusive

    def set(self, x: int, y: int, z: int, flag: int, value: bool) -> bool:
        """Set a flag value at world coordinates. Return True if set, False if out of bounds."""
        region_x = x >> 6
        region_y = y >> 6

        idx = self._get_index(region_x, region_y)
        if idx < 0 or idx >= len(self._region_maps):
            return False

        region_map = self._region_maps[idx]
        if region_map is None:
            return False

        # Bounds check
        local_x = x - region_map.min_x
        local_y = y - region_map.min_y
        if (
            local_x < 0
            or local_x >= REGION_SIZE
            or local_y < 0
            or local_y >= REGION_SIZE
            or z < 0
            or z >= region_map.plane_count
            or flag < 0
            or flag >= FLAG_COUNT
        ):
            return False

        flag_idx = (
            z * REGION_SIZE * REGION_SIZE + local_y * REGION_SIZE + local_x
        ) * FLAG_COUNT + flag
        region_map._flags[flag_idx] = value

        # Invalidate cache if we modified the cached region
        if region_x == self._cached_region_x and region_y == self._cached_region_y:
            self._cached_region = region_map

        return True

    def block_tile(
        self,
        x: int,
        y: int,
        z: int,
        north: bool = True,
        east: bool = True,
        south: bool = True,
        west: bool = True,
    ) -> int:
        """Block movement through a tile in specified directions. Return flags modified."""
        modified = 0

        if north and self.set(x, y, z, FLAG_NORTH, False):
            modified += 1

        if east and self.set(x, y, z, FLAG_EAST, False):
            modified += 1

        # Block coming from south = block north flag on tile below
        if south and self.set(x, y - 1, z, FLAG_NORTH, False):
            modified += 1

        # Block coming from west = block east flag on tile to the left
        if west and self.set(x - 1, y, z, FLAG_EAST, False):
            modified += 1

        return modified

    def apply_collision_blocks(self, blocks) -> int:
        """Apply collision blocks, creating virtual walls at locked doors. Return flags modified."""
        total_modified = 0

        for block in blocks:
            north = block.blocks_north()
            east = block.blocks_east()
            south = block.blocks_south()
            west = block.blocks_west()

            modified = self.block_tile(
                block.x, block.y, block.plane, north=north, east=east, south=south, west=west
            )
            total_modified += modified

        return total_modified

    def to_zip_file(self, zip_path: Path) -> None:
        """Save collision data to a ZIP file."""
        import zipfile

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, region_map in enumerate(self._region_maps):
                if region_map is None:
                    continue

                # Calculate region coordinates from index
                region_x = (idx % self._width_inclusive) + self.region_extents.min_x
                region_y = (idx // self._width_inclusive) + self.region_extents.min_y

                # Write region data
                filename = f"{region_x}_{region_y}"
                zf.writestr(filename, region_map.to_bytes())

    @classmethod
    def from_zip_file(cls, zip_path: Path) -> SplitFlagMap:
        """Load collision data from a ZIP file."""
        compressed_regions: dict[int, bytes] = {}

        min_x = float("inf")
        min_y = float("inf")
        max_x = 0
        max_y = 0

        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                # Skip directories
                if name.endswith("/"):
                    continue

                # Parse region coordinates from filename
                # Format: "regionX_regionY"
                parts = name.split("_")
                if len(parts) != 2:
                    continue

                try:
                    region_x = int(parts[0])
                    region_y = int(parts[1])
                except ValueError:
                    continue

                # Track extents
                min_x = min(min_x, region_x)
                min_y = min(min_y, region_y)
                max_x = max(max_x, region_x)
                max_y = max(max_y, region_y)

                # Load region data
                packed_pos = pack_region_position(region_x, region_y)
                compressed_regions[packed_pos] = zf.read(name)

        if not compressed_regions:
            raise ValueError(f"No regions found in {zip_path}")

        region_extents = RegionExtent(
            min_x=int(min_x), min_y=int(min_y), max_x=int(max_x), max_y=int(max_y)
        )

        return cls(compressed_regions, region_extents)
