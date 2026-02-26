"""Point types for world and screen coordinates."""

import math
from dataclasses import dataclass


@dataclass
class Point:
    """Represents a 3D world tile position with packed coordinate support.

    Packing format (15-bit, matches Java):
    - Bits 0-14: x coordinate (0-32767)
    - Bits 15-29: y coordinate (0-32767)
    - Bits 30-31: plane (0-3)
    """

    x: int
    y: int
    plane: int = 0

    def __post_init__(self):
        if not (0 <= self.x <= 32767):
            raise ValueError(f"X out of range: {self.x} (must be 0-32767)")
        if not (0 <= self.y <= 32767):
            raise ValueError(f"Y out of range: {self.y} (must be 0-32767)")
        if not (0 <= self.plane <= 3):
            raise ValueError(f"Plane out of range: {self.plane} (must be 0-3)")

    @classmethod
    def from_packed(cls, packed: int) -> Point:
        """Create a Point from a packed 32-bit integer."""
        if packed < 0:
            packed = packed + 2**32

        x = packed & 0x7FFF
        y = (packed >> 15) & 0x7FFF
        plane = (packed >> 30) & 0x3

        return cls(x=x, y=y, plane=plane)

    @property
    def packed(self) -> int:
        """Unsigned 32-bit packed representation."""
        return (self.x & 0x7FFF) | ((self.y & 0x7FFF) << 15) | ((self.plane & 0x3) << 30)

    @property
    def packed_signed(self) -> int:
        """Signed 32-bit packed representation."""
        packed = self.packed
        if packed >= 2**31:
            return packed - 2**32
        return packed

    def unpack(self) -> tuple[int, int, int]:
        """Return the (x, y, plane) tuple."""
        return (self.x, self.y, self.plane)

    def distance_to(self, other: Point) -> int:
        """Return the Chebyshev distance to another point."""
        dx = abs(self.x - other.x)
        dy = abs(self.y - other.y)
        return max(dx, dy)

    def is_nearby(self, other: Point, radius: int, same_plane: bool = True) -> bool:
        """Check whether another point is within the given radius."""
        if same_plane and self.plane != other.plane:
            return False

        return self.distance_to(other) <= radius

    def __eq__(self, other) -> bool:
        if isinstance(other, Point):
            return self.x == other.x and self.y == other.y and self.plane == other.plane
        return False

    def __hash__(self) -> int:
        return self.packed

    def __repr__(self) -> str:
        return f"Point(x={self.x}, y={self.y}, plane={self.plane})"


@dataclass
class Point3D:
    """Represents a 3D point with integer coordinates for rendering."""

    x: int
    y: int
    z: int

    def distance_to(self, other: Point3D) -> float:
        """Return the Euclidean distance to another 3D point."""
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def __repr__(self) -> str:
        return f"Point3D({self.x}, {self.y}, {self.z})"


@dataclass
class ScreenPoint:
    """Represents a 2D screen/UI pixel coordinate."""

    x: int
    y: int

    def distance_to(self, other: ScreenPoint) -> float:
        """Return the Euclidean distance to another screen point."""
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)


def pack_position(x: int, y: int, plane: int) -> int:
    """Pack x, y, plane into an unsigned 32-bit integer."""
    return (x & 0x7FFF) | ((y & 0x7FFF) << 15) | ((plane & 0x3) << 30)


def pack_position_signed(x: int, y: int, plane: int) -> int:
    """Pack x, y, plane into a signed 32-bit integer."""
    packed = pack_position(x, y, plane)
    if packed >= 2**31:
        return packed - 2**32
    return packed


def unpack_position(packed: int) -> tuple[int, int, int]:
    """Unpack a 32-bit integer into (x, y, plane)."""
    if packed < 0:
        packed = packed + 2**32

    x = packed & 0x7FFF
    y = (packed >> 15) & 0x7FFF
    plane = (packed >> 30) & 0x3

    return (x, y, plane)
