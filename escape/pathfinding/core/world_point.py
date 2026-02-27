"""World point coordinate packing and unpacking utilities."""

from __future__ import annotations

import sys
from typing import NamedTuple

# Constants
UNDEFINED: int = -1
"""Sentinel value indicating an undefined/invalid packed world point."""

# Bit masks and shifts for coordinate packing
_X_MASK: int = 0x7FFF  # 15 bits (32767)
_Y_MASK: int = 0x7FFF  # 15 bits (32767)
_PLANE_MASK: int = 0x3  # 2 bits (0-3)
_Y_SHIFT: int = 15
_PLANE_SHIFT: int = 30

# Maximum distance value (equivalent to Integer.MAX_VALUE in Java)
MAX_DISTANCE: int = sys.maxsize


class WorldPoint(NamedTuple):
    """Unpacked world point coordinates."""

    x: int
    y: int
    plane: int


class WorldArea(NamedTuple):
    """A rectangular area in the world."""

    x: int
    y: int
    width: int
    height: int
    plane: int


# =============================================================================
# Core Functions — Rust native or Numba JIT fallback
# =============================================================================

try:
    from escape.pathfinding._native import (
        distance_between,
        distance_between_2d,
        distance_between_2d_coords,
        distance_between_coords,
        distance_to_area,
        distance_to_area_2d,
        dxdy,
        pack_world_point,
        unpack_world_plane,
        unpack_world_point,
        unpack_world_x,
        unpack_world_y,
    )
except ImportError:
    from numba import njit

    @njit(cache=True)
    def pack_world_point(x: int, y: int, plane: int) -> int:
        """Pack x, y, plane coordinates into a single 32-bit integer."""
        return (x & 0x7FFF) | ((y & 0x7FFF) << 15) | ((plane & 0x3) << 30)

    @njit(cache=True)
    def unpack_world_x(packed: int) -> int:
        """Extract the x coordinate from a packed world point."""
        return packed & 0x7FFF

    @njit(cache=True)
    def unpack_world_y(packed: int) -> int:
        """Extract the y coordinate from a packed world point."""
        return (packed >> 15) & 0x7FFF

    @njit(cache=True)
    def unpack_world_plane(packed: int) -> int:
        """Extract the plane from a packed world point."""
        return (packed >> 30) & 0x3

    @njit(cache=True)
    def unpack_world_point(packed: int) -> tuple[int, int, int]:
        """Unpack a packed world point into (x, y, plane) tuple."""
        x = packed & 0x7FFF
        y = (packed >> 15) & 0x7FFF
        plane = (packed >> 30) & 0x3
        return (x, y, plane)

    @njit(cache=True)
    def dxdy(packed: int, dx: int, dy: int) -> int:
        """Offset a packed world point by (dx, dy) on the same plane."""
        x = packed & 0x7FFF
        y = (packed >> 15) & 0x7FFF
        plane = (packed >> 30) & 0x3
        return pack_world_point(x + dx, y + dy, plane)

    @njit(cache=True)
    def distance_between_2d_coords(x1: int, y1: int, x2: int, y2: int, diagonal: int = 1) -> int:
        """Compute 2D distance between two coordinate pairs.

        Uses Chebyshev (diagonal=1) or Manhattan (diagonal=2) metric.
        """
        dx = abs(x1 - x2)
        dy = abs(y1 - y2)

        if diagonal == 1:
            return max(dx, dy)
        elif diagonal == 2:
            return dx + dy

        return 2147483647

    @njit(cache=True)
    def distance_between_coords(
        x1: int, y1: int, plane1: int, x2: int, y2: int, plane2: int, diagonal: int = 1
    ) -> int:
        """Compute distance between two 3D coordinate sets, or MAX_DISTANCE if planes differ."""
        if plane1 != plane2:
            return 2147483647
        return distance_between_2d_coords(x1, y1, x2, y2, diagonal)

    @njit(cache=True)
    def distance_between(packed1: int, packed2: int, diagonal: int = 1) -> int:
        """Compute distance between two packed world points, or MAX_DISTANCE if planes differ."""
        x1 = packed1 & 0x7FFF
        y1 = (packed1 >> 15) & 0x7FFF
        plane1 = (packed1 >> 30) & 0x3

        x2 = packed2 & 0x7FFF
        y2 = (packed2 >> 15) & 0x7FFF
        plane2 = (packed2 >> 30) & 0x3

        return distance_between_coords(x1, y1, plane1, x2, y2, plane2, diagonal)

    @njit(cache=True)
    def distance_between_2d(packed1: int, packed2: int, diagonal: int = 1) -> int:
        """Compute 2D distance between two packed world points (ignoring plane)."""
        x1 = packed1 & 0x7FFF
        y1 = (packed1 >> 15) & 0x7FFF

        x2 = packed2 & 0x7FFF
        y2 = (packed2 >> 15) & 0x7FFF

        return distance_between_2d_coords(x1, y1, x2, y2, diagonal)

    @njit(cache=True)
    def distance_to_area_2d(
        packed: int, area_x: int, area_y: int, area_width: int, area_height: int
    ) -> int:
        """Compute 2D Chebyshev distance from a packed point to a rectangular area (0 if inside)."""
        x = packed & 0x7FFF
        y = (packed >> 15) & 0x7FFF

        area_max_x = area_x + area_width - 1
        area_max_y = area_y + area_height - 1

        dx = max(max(area_x - x, 0), x - area_max_x)
        dy = max(max(area_y - y, 0), y - area_max_y)

        return max(dx, dy)

    @njit(cache=True)
    def distance_to_area(
        packed: int,
        area_x: int,
        area_y: int,
        area_width: int,
        area_height: int,
        area_plane: int,
    ) -> int:
        """Compute Chebyshev distance from a packed point to a rectangular area, or MAX_DISTANCE if planes differ."""
        plane = (packed >> 30) & 0x3
        if plane != area_plane:
            return 2147483647
        return distance_to_area_2d(packed, area_x, area_y, area_width, area_height)


# =============================================================================
# Non-JIT Helper Functions (for convenience)
# =============================================================================


def pack_point(point: WorldPoint | tuple[int, int, int] | None) -> int:
    """Pack a WorldPoint or tuple into a packed integer, or UNDEFINED (-1) if None."""
    if point is None:
        return UNDEFINED
    if isinstance(point, WorldPoint):
        return pack_world_point(point.x, point.y, point.plane)
    return pack_world_point(point[0], point[1], point[2])


def unpack_to_world_point(packed: int) -> WorldPoint:
    """Unpack a packed integer into a WorldPoint namedtuple."""
    x, y, plane = unpack_world_point(packed)
    return WorldPoint(x, y, plane)


def distance_to_world_area(packed: int, area: WorldArea) -> int:
    """Compute distance from a packed point to a WorldArea."""
    return distance_to_area(packed, area.x, area.y, area.width, area.height, area.plane)


def distance_between_points(p1: WorldPoint, p2: WorldPoint, diagonal: int = 1) -> int:
    """Compute distance between two WorldPoint objects."""
    return distance_between_coords(p1.x, p1.y, p1.plane, p2.x, p2.y, p2.plane, diagonal)
