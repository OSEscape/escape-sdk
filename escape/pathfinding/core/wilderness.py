"""Wilderness area checking utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from escape.pathfinding.core.world_point import distance_to_area_2d

if TYPE_CHECKING:
    from collections.abc import Iterable

# =============================================================================
# Wilderness Area Definitions
# =============================================================================

# Main wilderness areas (above ground and underground)
WILDERNESS_ABOVE_GROUND = (2944, 3525, 448, 448, 0)  # (x, y, width, height, plane)
WILDERNESS_UNDERGROUND = (2944, 9918, 518, 458, 0)

# Ferox Enclave - safe zone within wilderness
FEROX_ENCLAVE_1 = (3123, 3622, 2, 10, 0)
FEROX_ENCLAVE_2 = (3125, 3617, 16, 23, 0)
FEROX_ENCLAVE_3 = (3138, 3636, 18, 10, 0)
FEROX_ENCLAVE_4 = (3141, 3625, 14, 11, 0)
FEROX_ENCLAVE_5 = (3141, 3619, 7, 6, 0)

FEROX_ENCLAVE_AREAS = (
    FEROX_ENCLAVE_1,
    FEROX_ENCLAVE_2,
    FEROX_ENCLAVE_3,
    FEROX_ENCLAVE_4,
    FEROX_ENCLAVE_5,
)

# Areas that look like wilderness but aren't (edge cases)
NOT_WILDERNESS_1 = (2997, 3525, 34, 9, 0)
NOT_WILDERNESS_2 = (3005, 3534, 21, 10, 0)
NOT_WILDERNESS_3 = (3000, 3534, 5, 5, 0)
NOT_WILDERNESS_4 = (3031, 3525, 2, 2, 0)

NOT_WILDERNESS_AREAS = (
    NOT_WILDERNESS_1,
    NOT_WILDERNESS_2,
    NOT_WILDERNESS_3,
    NOT_WILDERNESS_4,
)

# Higher wilderness level boundaries (for teleport restrictions)
# Level 20+ wilderness (most teleports blocked)
WILDERNESS_ABOVE_GROUND_LEVEL_20 = (2944, 3680, 448, 448, 0)
WILDERNESS_UNDERGROUND_LEVEL_20 = (2944, 10075, 320, 442, 0)

# Level 30+ wilderness (all teleports blocked except specific items)
WILDERNESS_ABOVE_GROUND_LEVEL_30 = (2944, 3760, 448, 448, 0)
WILDERNESS_UNDERGROUND_LEVEL_30 = (2944, 10155, 320, 442, 0)

# =============================================================================
# Helper Functions
# =============================================================================


def _in_area(packed: int, area: tuple[int, int, int, int, int]) -> bool:
    """Check if packed point is inside an area (distance == 0)."""
    return distance_to_area_2d(packed, area[0], area[1], area[2], area[3]) == 0


def _in_any_area(packed: int, areas: tuple) -> bool:
    """Check if packed point is inside any of the areas."""
    return any(_in_area(packed, area) for area in areas)


# =============================================================================
# Public API
# =============================================================================


def is_in_wilderness(packed: int) -> bool:
    """Check if a packed world point is in the Wilderness (excludes safe zones)."""
    # Check if in main wilderness area (above ground)
    in_wildy_above = _in_area(packed, WILDERNESS_ABOVE_GROUND)

    if in_wildy_above:
        # Exclude Ferox Enclave (safe zone)
        if _in_any_area(packed, FEROX_ENCLAVE_AREAS):
            return False
        # Exclude edge areas that aren't actually wilderness
        return not _in_any_area(packed, NOT_WILDERNESS_AREAS)

    # Check underground wilderness
    return _in_area(packed, WILDERNESS_UNDERGROUND)


def is_in_wilderness_any(packed_points: Iterable[int]) -> bool:
    """Check if any of the packed points are in the Wilderness."""
    return any(is_in_wilderness(p) for p in packed_points)


def is_in_level_20_wilderness(packed: int) -> bool:
    """Check if a packed point is in level 20+ Wilderness."""
    return _in_area(packed, WILDERNESS_ABOVE_GROUND_LEVEL_20) or _in_area(
        packed, WILDERNESS_UNDERGROUND_LEVEL_20
    )


def is_in_level_30_wilderness(packed: int) -> bool:
    """Check if a packed point is in level 30+ Wilderness."""
    return _in_area(packed, WILDERNESS_ABOVE_GROUND_LEVEL_30) or _in_area(
        packed, WILDERNESS_UNDERGROUND_LEVEL_30
    )


def get_wilderness_level(packed: int) -> int:
    """Get the wilderness level at a packed point (0 if not in wilderness)."""
    if not is_in_wilderness(packed):
        return 0

    # Extract y coordinate
    y = (packed >> 15) & 0x7FFF

    # Above ground wilderness starts at y=3525
    if _in_area(packed, WILDERNESS_ABOVE_GROUND):
        return max(1, (y - 3520) // 8)

    # Underground wilderness
    if _in_area(packed, WILDERNESS_UNDERGROUND):
        return max(1, (y - 9912) // 8)

    return 0


def can_teleport_at_level(wilderness_level: int, max_level: int = 20) -> bool:
    """Check if teleportation is allowed at a given wilderness level."""
    return wilderness_level <= max_level
