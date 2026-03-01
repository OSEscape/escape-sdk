"""Core utilities for coordinate packing, enums, and player context."""

from escape.pathfinding.core.enums import OrdinalDirection, TransportType

# world_point imports are deferred to avoid circular imports at import time.
# Import directly from .world_point when needed:
#   from escape.pathfinding.core.world_point import pack_world_point


def __getattr__(name: str):
    """Lazy import for world_point symbols."""
    _world_point_names = {
        "WorldArea",
        "WorldPoint",
        "distance_between",
        "distance_between_2d",
        "dxdy",
        "pack_world_point",
        "unpack_world_plane",
        "unpack_world_point",
        "unpack_world_x",
        "unpack_world_y",
    }
    if name in _world_point_names:
        from escape.pathfinding.core import world_point

        return getattr(world_point, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "OrdinalDirection",
    "TransportType",
]
