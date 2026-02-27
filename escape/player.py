"""Local player monitoring and state tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING

from escape._math import _chebyshev, _combat_level

if TYPE_CHECKING:
    from escape.skills import Skills


class Player:
    """Local player data module.

    Provides reactive access to position, energy, and current interactions.
    """

    def __init__(self, skills: Skills):
        """Initialize the Player controller."""
        from escape._services import Services

        self._cache = Services.get().cache
        self._skills = skills

    @property
    def position(self) -> tuple[int, int, int]:
        """Return the current absolute World coordinates (x, y, plane)."""
        return self._cache.world_position

    @property
    def scene_position(self) -> tuple[int, int] | None:
        """Return the current scene-relative coordinates (x, y)."""
        return self._cache.position

    @property
    def energy(self) -> int:
        """Return current run energy (0-100)."""
        return self._cache.energy or 0

    @property
    def is_logged_in(self) -> bool:
        """True if the player is currently logged into a game world."""
        return self._cache.game_state == "LOGGED_IN"

    @property
    def interacting(self):
        """Return the NPC the player is currently interacting with."""
        return self._cache.interacting_npc

    @property
    def animation(self) -> int:
        """Return the local player's current animation ID."""
        return self._cache.get_actor_animation("local")

    @property
    def health(self) -> int:
        """Return the local player's current Hitpoints level."""
        return self._skills.get_level("Hitpoints")

    @property
    def prayer(self) -> int:
        """Return the local player's current Prayer points."""
        return self._skills.get_level("Prayer")

    def distance_to(self, x: int, y: int) -> int | None:
        """Return Chebyshev distance to the given absolute World tile."""
        pos = self.position
        if not pos:
            return None
        return _chebyshev(x, y, pos[0], pos[1])

    def is_at(self, x: int, y: int, plane: int | None = None) -> bool:
        """Check if the player is standing on the exact specified tile."""
        pos = self.position
        if not pos:
            return False
        return pos[0] == x and pos[1] == y and (plane is None or pos[2] == plane)

    def is_nearby(self, x: int, y: int, radius: int, plane: int | None = None) -> bool:
        """Check if the player is within a specific radius of a tile."""
        dist = self.distance_to(x, y)
        if dist is None:
            return False
        if plane is not None and self.position[2] != plane:
            return False
        return dist <= radius

    @property
    def combat_level(self) -> int:
        """Return the player's combat level."""
        get = self._skills.get_level
        return _combat_level(
            attack=get("Attack"),
            strength=get("Strength"),
            defence=get("Defence"),
            hitpoints=get("Hitpoints"),
            prayer=get("Prayer"),
            ranged=get("Ranged"),
            magic=get("Magic"),
        )
