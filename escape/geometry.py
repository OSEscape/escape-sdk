"""Geometry types: Shape, Box, Circle, Polygon, Quad."""

import math
import random
from dataclasses import dataclass

from escape.point import ScreenPoint


class Shape:
    """Base class for geometry shapes with shared interaction methods."""

    def random_point(self) -> ScreenPoint:
        raise NotImplementedError

    def center(self) -> ScreenPoint:
        raise NotImplementedError

    def interact(self, *, option: str | None = None, action: str | None = None) -> bool:
        """Click a random point inside this shape."""
        from escape.interaction import interact

        return interact(self.random_point(), option=option, action=action)

    def hover(self, option: str | None = None, action: str | None = None) -> bool:
        """Move the mouse to a random point inside this shape."""
        from escape.interaction import hover

        return hover(self.random_point(), option=option, action=action)

    def right_click(self) -> None:
        """Right-click a random point inside this shape."""
        from escape.interaction import right_click

        right_click(self.random_point())


@dataclass
class Box(Shape):
    """Represents a rectangular area (axis-aligned box) with integer coordinates."""

    x: int
    y: int
    width: int
    height: int

    def area(self) -> int:
        """Return the area in pixels."""
        return self.width * self.height

    def center(self) -> ScreenPoint:
        """Return the center point."""
        return ScreenPoint(self.x + self.width // 2, self.y + self.height // 2)

    def contains(self, other: ScreenPoint | Box) -> bool:
        """Check if a point or box is inside this box."""
        if isinstance(other, Box):
            return (
                self.x <= other.x
                and other.x + other.width <= self.x + self.width
                and self.y <= other.y
                and other.y + other.height <= self.y + self.height
            )
        return self.x <= other.x < self.x + self.width and self.y <= other.y < self.y + self.height

    def random_point(self) -> ScreenPoint:
        """Return a random point inside this box."""
        return ScreenPoint(
            random.randrange(self.x, self.x + self.width),
            random.randrange(self.y, self.y + self.height),
        )

    def __repr__(self) -> str:
        return f"Box({self.x}, {self.y}, {self.width}, {self.height})"


@dataclass
class Circle(Shape):
    """Represents a circle with integer center coordinates and float radius."""

    center_x: int
    center_y: int
    radius: float

    def center(self) -> ScreenPoint:
        """Return the center point."""
        return ScreenPoint(self.center_x, self.center_y)

    def area(self) -> float:
        """Return the area."""
        return math.pi * self.radius * self.radius

    def contains(self, point: ScreenPoint) -> bool:
        """Check if a point is inside this circle."""
        dx = point.x - self.center_x
        dy = point.y - self.center_y
        return math.sqrt(dx * dx + dy * dy) <= self.radius

    def random_point(self) -> ScreenPoint:
        """Return a random point inside this circle."""
        r = self.radius * math.sqrt(random.random())
        theta = random.uniform(0, 2 * math.pi)

        x = self.center_x + int(r * math.cos(theta))
        y = self.center_y + int(r * math.sin(theta))

        return ScreenPoint(x, y)

    def __repr__(self) -> str:
        return f"Circle(center=({self.center_x}, {self.center_y}), radius={self.radius})"


@dataclass
class Polygon(Shape):
    """Represents an arbitrary polygon defined by n vertices."""

    vertices: list[ScreenPoint]

    def __post_init__(self):
        if len(self.vertices) < 3:
            raise ValueError("Polygon must have at least 3 vertices")

    def center(self) -> ScreenPoint:
        """Return the centroid."""
        x_sum = sum(v.x for v in self.vertices)
        y_sum = sum(v.y for v in self.vertices)
        n = len(self.vertices)
        return ScreenPoint(x_sum // n, y_sum // n)

    def bounds(self) -> tuple[int, int, int, int]:
        """Return the axis-aligned bounding box as (min_x, min_y, max_x, max_y)."""
        min_x = min(v.x for v in self.vertices)
        min_y = min(v.y for v in self.vertices)
        max_x = max(v.x for v in self.vertices)
        max_y = max(v.y for v in self.vertices)
        return (min_x, min_y, max_x, max_y)

    def contains(self, point: ScreenPoint) -> bool:
        """Check if a point is inside this polygon."""
        x, y = point.x, point.y
        n = len(self.vertices)
        inside = False

        p1x, p1y = self.vertices[0].x, self.vertices[0].y
        for i in range(1, n + 1):
            p2x, p2y = self.vertices[i % n].x, self.vertices[i % n].y
            if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    def area(self) -> float:
        """Return the area using the shoelace formula."""
        n = len(self.vertices)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.vertices[i].x * self.vertices[j].y
            area -= self.vertices[j].x * self.vertices[i].y
        return abs(area) / 2.0

    def random_point(self) -> ScreenPoint:
        """Return a random point inside this polygon."""
        min_x, min_y, max_x, max_y = self.bounds()

        max_attempts = 1000
        for _ in range(max_attempts):
            x = random.randint(min_x, max_x)
            y = random.randint(min_y, max_y)
            point = ScreenPoint(x, y)
            if self.contains(point):
                return point

        return self.center()

    def __repr__(self) -> str:
        return f"Polygon({len(self.vertices)} vertices, area={self.area():.2f})"


@dataclass
class Quad(Shape):
    """Represents a quadrilateral defined by exactly 4 vertices in order."""

    p1: ScreenPoint
    p2: ScreenPoint
    p3: ScreenPoint
    p4: ScreenPoint

    @classmethod
    def from_points(cls, points: list[ScreenPoint]) -> Quad:
        """Create a quad from a list of four screen points."""
        if len(points) != 4:
            raise ValueError(f"Quad requires exactly 4 points, got {len(points)}")
        return cls(points[0], points[1], points[2], points[3])

    @classmethod
    def from_coords(cls, coords: list[tuple[int, int]]) -> Quad:
        """Create a quad from a list of four (x, y) tuples."""
        if len(coords) != 4:
            raise ValueError(f"Quad requires exactly 4 coordinates, got {len(coords)}")
        points = [ScreenPoint(x, y) for x, y in coords]
        return cls(points[0], points[1], points[2], points[3])

    @classmethod
    def from_arrays(cls, x_coords: list[int], y_coords: list[int]) -> Quad:
        """Create a quad from separate x and y coordinate arrays."""
        if len(x_coords) != 4 or len(y_coords) != 4:
            raise ValueError("Quad requires exactly 4 x and 4 y coordinates")
        return cls(
            ScreenPoint(x_coords[0], y_coords[0]),
            ScreenPoint(x_coords[1], y_coords[1]),
            ScreenPoint(x_coords[2], y_coords[2]),
            ScreenPoint(x_coords[3], y_coords[3]),
        )

    @property
    def vertices(self) -> list[ScreenPoint]:
        """Four corner points."""
        return [self.p1, self.p2, self.p3, self.p4]

    def center(self) -> ScreenPoint:
        """Return the center point."""
        x = (self.p1.x + self.p2.x + self.p3.x + self.p4.x) // 4
        y = (self.p1.y + self.p2.y + self.p3.y + self.p4.y) // 4
        return ScreenPoint(x, y)

    def bounds(self) -> tuple[int, int, int, int]:
        """Return the axis-aligned bounding box as (min_x, min_y, max_x, max_y)."""
        xs = [self.p1.x, self.p2.x, self.p3.x, self.p4.x]
        ys = [self.p1.y, self.p2.y, self.p3.y, self.p4.y]
        return (min(xs), min(ys), max(xs), max(ys))

    def _sign(self, p1x: int, p1y: int, p2x: int, p2y: int, p3x: int, p3y: int) -> float:
        return (p1x - p3x) * (p2y - p3y) - (p2x - p3x) * (p1y - p3y)

    def _point_in_triangle(
        self, px: int, py: int, v1: ScreenPoint, v2: ScreenPoint, v3: ScreenPoint
    ) -> bool:
        d1 = self._sign(px, py, v1.x, v1.y, v2.x, v2.y)
        d2 = self._sign(px, py, v2.x, v2.y, v3.x, v3.y)
        d3 = self._sign(px, py, v3.x, v3.y, v1.x, v1.y)

        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)

        return not (has_neg and has_pos)

    def contains(self, point: ScreenPoint) -> bool:
        """Check if a point is inside this quad."""
        px, py = point.x, point.y

        return self._point_in_triangle(
            px, py, self.p1, self.p2, self.p3
        ) or self._point_in_triangle(px, py, self.p1, self.p3, self.p4)

    def area(self) -> float:
        """Return the area using the shoelace formula."""
        area = 0.0
        vertices = self.vertices
        n = 4
        for i in range(n):
            j = (i + 1) % n
            area += vertices[i].x * vertices[j].y
            area -= vertices[j].x * vertices[i].y
        return abs(area) / 2.0

    def random_point(self) -> ScreenPoint:
        """Return a random point inside this quad."""
        u = random.random()
        v = random.random()

        x = int(
            (1 - u) * (1 - v) * self.p1.x
            + u * (1 - v) * self.p2.x
            + u * v * self.p3.x
            + (1 - u) * v * self.p4.x
        )
        y = int(
            (1 - u) * (1 - v) * self.p1.y
            + u * (1 - v) * self.p2.y
            + u * v * self.p3.y
            + (1 - u) * v * self.p4.y
        )

        point = ScreenPoint(x, y)

        if self.contains(point):
            return point

        min_x, min_y, max_x, max_y = self.bounds()
        for _ in range(100):
            x = random.randint(min_x, max_x)
            y = random.randint(min_y, max_y)
            point = ScreenPoint(x, y)
            if self.contains(point):
                return point

        return self.center()

    def to_polygon(self) -> Polygon:
        """Convert to a polygon."""
        return Polygon(self.vertices)

    def is_convex(self) -> bool:
        """Check if this quad is convex."""
        vertices = self.vertices

        def cross_product(o: ScreenPoint, a: ScreenPoint, b: ScreenPoint) -> float:
            return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)

        signs = []
        for i in range(4):
            o = vertices[i]
            a = vertices[(i + 1) % 4]
            b = vertices[(i + 2) % 4]
            cross = cross_product(o, a, b)
            if cross != 0:
                signs.append(cross > 0)

        return len(set(signs)) <= 1

    def __repr__(self) -> str:
        return f"Quad({self.p1}, {self.p2}, {self.p3}, {self.p4})"
