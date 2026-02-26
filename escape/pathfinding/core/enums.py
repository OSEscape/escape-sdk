"""Enumerations for the pathfinding system."""

from __future__ import annotations

from enum import Enum, auto


class TransportType(Enum):
    """Types of transport methods available in OSRS."""

    TRANSPORT = auto()  # Generic transport (doors, stairs, etc.)
    AGILITY_SHORTCUT = auto()  # Agility shortcuts
    GRAPPLE_SHORTCUT = auto()  # Grapple shortcuts (require crossbow + grapple)
    BOAT = auto()  # Boats (e.g., Port Sarim to Karamja)
    CANOE = auto()  # Canoe stations
    CHARTER_SHIP = auto()  # Charter ships (cost gold)
    SHIP = auto()  # Ships (scheduled routes)
    FAIRY_RING = auto()  # Fairy ring network
    GNOME_GLIDER = auto()  # Gnome glider network
    HOT_AIR_BALLOON = auto()  # Hot air balloon routes
    MAGIC_CARPET = auto()  # Magic carpet rides
    MAGIC_MUSHTREE = auto()  # Mushroom trees (Fossil Island)
    MINECART = auto()  # Minecart systems (Keldagrim, etc.)
    QUETZAL = auto()  # Quetzal transport (Varlamore)
    SEASONAL_TRANSPORTS = auto()  # Seasonal event transports
    SPIRIT_TREE = auto()  # Spirit tree network
    TELEPORTATION_BOX = auto()  # Teleport boxes (fixed location)
    TELEPORTATION_ITEM = auto()  # Teleport items (tablets, jewelry, etc.)
    TELEPORTATION_LEVER = auto()  # Teleport levers (fixed origin)
    TELEPORTATION_MINIGAME = auto()  # Minigame teleports (group finder)
    TELEPORTATION_PORTAL = auto()  # Teleport portals (fixed location)
    TELEPORTATION_PORTAL_POH = auto()  # POH portal nexus
    TELEPORTATION_SPELL = auto()  # Magic spellbook teleports
    WILDERNESS_OBELISK = auto()  # Wilderness obelisks

    @property
    def is_teleport(self) -> bool:
        """Check if this transport type is a teleport.

        Teleports can be used from any location (centered on player)
        and have wilderness level limits. Levers, portals and wilderness
        obelisks are NOT teleports because they have pre-defined origins
        and no wilderness limits.
        """
        return self in (
            TransportType.TELEPORTATION_ITEM,
            TransportType.TELEPORTATION_MINIGAME,
            TransportType.TELEPORTATION_SPELL,
        )


class OrdinalDirection(Enum):
    """Eight cardinal and ordinal directions with (dx, dy) offsets."""

    WEST = (-1, 0)
    EAST = (1, 0)
    SOUTH = (0, -1)
    NORTH = (0, 1)
    SOUTH_WEST = (-1, -1)
    SOUTH_EAST = (1, -1)
    NORTH_WEST = (-1, 1)
    NORTH_EAST = (1, 1)

    @property
    def dx(self) -> int:
        """X offset for this direction."""
        return self.value[0]

    @property
    def dy(self) -> int:
        """Y offset for this direction."""
        return self.value[1]

    @property
    def offset(self) -> tuple[int, int]:
        """(dx, dy) offset tuple."""
        return self.value


# Pre-computed direction lists for efficient iteration
CARDINAL_DIRECTIONS: tuple[OrdinalDirection, ...] = (
    OrdinalDirection.WEST,
    OrdinalDirection.EAST,
    OrdinalDirection.SOUTH,
    OrdinalDirection.NORTH,
)

DIAGONAL_DIRECTIONS: tuple[OrdinalDirection, ...] = (
    OrdinalDirection.SOUTH_WEST,
    OrdinalDirection.SOUTH_EAST,
    OrdinalDirection.NORTH_WEST,
    OrdinalDirection.NORTH_EAST,
)

ALL_DIRECTIONS: tuple[OrdinalDirection, ...] = CARDINAL_DIRECTIONS + DIAGONAL_DIRECTIONS

# Pre-computed dx/dy lookup dicts for hot path optimization
# Accessing dict[key] is faster than enum.property
DIRECTION_DX: dict[OrdinalDirection, int] = {d: d.value[0] for d in OrdinalDirection}
DIRECTION_DY: dict[OrdinalDirection, int] = {d: d.value[1] for d in OrdinalDirection}

# Pre-computed list of (direction, dx, dy) for iteration without property access
ALL_DIRECTIONS_WITH_OFFSETS: tuple[tuple[OrdinalDirection, int, int], ...] = tuple(
    (d, d.value[0], d.value[1]) for d in ALL_DIRECTIONS
)
