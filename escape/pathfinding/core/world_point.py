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
# Core Functions — Rust native extension
# =============================================================================

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
