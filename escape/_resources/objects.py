"""Game Objects accessor functions for OSRS object definitions and locations."""

import sqlite3
from dataclasses import dataclass
from typing import Any

from escape._logger import logger
from escape.point import pack_position_signed, unpack_position

__all__ = [
    "ResourceObject",
    "close",
    "find_object_at",
    "query",
    "set_db_connection",
]

# Module-level database connection (loaded by cache_manager at init)
_db_connection: sqlite3.Connection | None = None


@dataclass(frozen=True, slots=True)
class ResourceObject:
    """A static object spawn from the cache database. Coordinates are the SW corner."""

    id: int
    name: str
    x: int
    y: int
    plane: int
    size_x: int
    size_y: int
    orientation: int

    @property
    def tiles(self) -> list[tuple[int, int, int]]:
        """All tiles occupied by this object, accounting for orientation."""
        if self.orientation == 1 or self.orientation == 3:
            sx, sy = self.size_y, self.size_x
        else:
            sx, sy = self.size_x, self.size_y
        return [
            (self.x + dx, self.y + dy, self.plane)
            for dx in range(sx)
            for dy in range(sy)
        ]


def query(
    ids: list[int] | None = None,
    names: list[str] | None = None,
    actions: list[str] | None = None,
    x: int | None = None,
    y: int | None = None,
    plane: int = 0,
    radius: int = 10,
) -> list[ResourceObject]:
    """Query object spawns from the static cache database.

    All filters are optional and combined with AND. When no spatial filter
    (x/y) is given, searches globally.
    """
    if _db_connection is None:
        logger.error("Objects database not loaded")
        return []

    where_clauses: list[str] = []
    params: list[Any] = []

    # Spatial filter — packed-position range scan per X column
    if x is not None and y is not None:
        min_x = max(0, x - radius)
        max_x = min(32767, x + radius)
        min_y = max(0, y - radius)
        max_y = min(32767, y + radius)

        ranges = []
        for curr_x in range(min_x, max_x + 1):
            min_packed = pack_position_signed(curr_x, min_y, plane)
            max_packed = pack_position_signed(curr_x, max_y, plane)
            ranges.append((min_packed, max_packed))

        or_clauses = " OR ".join(["(o.coord BETWEEN ? AND ?)"] * len(ranges))
        where_clauses.append(f"({or_clauses})")
        for min_p, max_p in ranges:
            params.extend([min_p, max_p])

    if ids:
        placeholders = ", ".join(["?"] * len(ids))
        where_clauses.append(f"o.object_id IN ({placeholders})")
        params.extend(ids)

    if names:
        name_clauses = " OR ".join(["LOWER(n.name) = LOWER(?)"] * len(names))
        where_clauses.append(f"({name_clauses})")
        params.extend(names)

    need_actions_join = bool(actions)
    if actions:
        action_clauses = " OR ".join(["oas.action = ?"] * len(actions))
        where_clauses.append(f"({action_clauses})")
        params.extend(actions)

    where = " AND ".join(where_clauses) if where_clauses else "1=1"
    actions_join = "JOIN object_action_slots oas ON oas.object_id = o.object_id" if need_actions_join else ""

    sql = f"""
        SELECT DISTINCT o.coord, o.object_id, o.size_x, o.size_y, o.orientation, n.name
        FROM objects o
        LEFT JOIN names n ON o.name_id = n.id
        {actions_join}
        WHERE {where}
    """

    cursor = _db_connection.cursor()
    cursor.execute(sql, params)

    results = []
    for row in cursor.fetchall():
        obj_x, obj_y, obj_plane = unpack_position(row["coord"])
        results.append(
            ResourceObject(
                id=row["object_id"],
                name=row["name"] or "",
                x=obj_x,
                y=obj_y,
                plane=obj_plane,
                size_x=row["size_x"],
                size_y=row["size_y"],
                orientation=row["orientation"],
            )
        )

    return results


def find_object_at(x: int, y: int, plane: int) -> ResourceObject | None:
    """Find the ResourceObject whose footprint contains the given world tile."""
    for obj in query(x=x, y=y, plane=plane, radius=5):
        if (x, y, plane) in obj.tiles:
            return obj
    return None


def close():
    """Close database connection (called at shutdown)."""
    global _db_connection
    if _db_connection:
        _db_connection.close()
        _db_connection = None


def set_db_connection(conn: sqlite3.Connection) -> None:
    """Set the database connection (called by cache_manager during initialization)."""
    global _db_connection
    _db_connection = conn
    _db_connection.row_factory = sqlite3.Row
