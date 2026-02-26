"""Flag map for storing per-tile collision flags."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# OSRS region size in tiles
REGION_SIZE = 64

# Number of flags per tile (north and east)
FLAG_COUNT = 2

# Flag indices
FLAG_NORTH = 0
FLAG_EAST = 1

# =============================================================================
# FlagMap - Single Region
# =============================================================================


class FlagMap:
    """Collision flags for a single 64x64 region."""

    __slots__ = ("_flags", "min_x", "min_y", "plane_count")

    def __init__(self, min_x: int, min_y: int, plane_count: int = 4, data: bytes | None = None):
        """Create a FlagMap."""
        self.min_x = min_x
        self.min_y = min_y

        if data is not None:
            # Load from bytes - convert to numpy array
            # IMPORTANT: Use bitorder='little' to match Java's BitSet.valueOf()
            # which uses little-endian bit ordering within bytes (LSB first)
            self._flags = np.unpackbits(
                np.frombuffer(data, dtype=np.uint8), bitorder="little"
            ).astype(np.bool_)

            # Calculate plane count from data size
            total_flags = len(self._flags)
            flags_per_plane = REGION_SIZE * REGION_SIZE * FLAG_COUNT
            self.plane_count = (total_flags + flags_per_plane - 1) // flags_per_plane

            # Ensure array is correct size
            expected_size = self.plane_count * flags_per_plane
            if len(self._flags) < expected_size:
                # Pad with zeros if needed
                padded = np.zeros(expected_size, dtype=np.bool_)
                padded[: len(self._flags)] = self._flags
                self._flags = padded
            elif len(self._flags) > expected_size:
                self._flags = self._flags[:expected_size]
        else:
            self.plane_count = plane_count
            # Create empty flag array
            total_size = REGION_SIZE * REGION_SIZE * plane_count * FLAG_COUNT
            self._flags = np.zeros(total_size, dtype=np.bool_)

    def get(self, x: int, y: int, z: int, flag: int) -> bool:
        """Get a flag value."""
        # Bounds check
        if (
            x < self.min_x
            or x >= self.min_x + REGION_SIZE
            or y < self.min_y
            or y >= self.min_y + REGION_SIZE
            or z < 0
            or z >= self.plane_count
            or flag < 0
            or flag >= FLAG_COUNT
        ):
            return False

        idx = self._index(x, y, z, flag)
        return bool(self._flags[idx])

    def set(self, x: int, y: int, z: int, flag: int, value: bool) -> None:
        """Set a flag value."""
        idx = self._index(x, y, z, flag)
        self._flags[idx] = value

    def _index(self, x: int, y: int, z: int, flag: int) -> int:
        """Calculate array index for a flag."""
        return (
            z * REGION_SIZE * REGION_SIZE + (y - self.min_y) * REGION_SIZE + (x - self.min_x)
        ) * FLAG_COUNT + flag

    def to_bytes(self) -> bytes:
        """Convert flags to bytes for serialization."""
        # Pack bits into bytes using little-endian to match Java's BitSet
        packed = np.packbits(self._flags.astype(np.uint8), bitorder="little")
        return packed.tobytes()


# =============================================================================
# RegionExtent
# =============================================================================


@dataclass(frozen=True, slots=True)
class RegionExtent:
    """Extent of loaded regions in region coordinates."""

    min_x: int
    min_y: int
    max_x: int
    max_y: int

    @property
    def width(self) -> int:
        """Width in regions (exclusive)."""
        return self.max_x - self.min_x

    @property
    def height(self) -> int:
        """Height in regions (exclusive)."""
        return self.max_y - self.min_y


# =============================================================================
# Helper Functions
# =============================================================================


def pack_region_position(region_x: int, region_y: int) -> int:
    """Pack region coordinates into a single integer."""
    return (region_x & 0xFFFF) | ((region_y & 0xFFFF) << 16)


def unpack_region_x(packed: int) -> int:
    """Unpack region X from packed position."""
    return packed & 0xFFFF


def unpack_region_y(packed: int) -> int:
    """Unpack region Y from packed position."""
    return (packed >> 16) & 0xFFFF
