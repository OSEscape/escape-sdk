from escape._models import Skill
from escape.gametab import GameTab, GameTabs
from escape.timing import wait_until

SKILL_NAMES: list[str] = [
    "Attack",
    "Defence",
    "Strength",
    "Hitpoints",
    "Ranged",
    "Prayer",
    "Magic",
    "Cooking",
    "Woodcutting",
    "Fletching",
    "Fishing",
    "Firemaking",
    "Crafting",
    "Smithing",
    "Mining",
    "Herblore",
    "Agility",
    "Thieving",
    "Slayer",
    "Farming",
    "Runecrafting",
    "Hunter",
    "Construction",
    "Sailing",
]


class Skills(GameTabs):
    """Skills tab for viewing levels and experience."""

    TAB_TYPE = GameTab.SKILLS

    def __init__(self):
        super().__init__()
        self._last_total_xp: int | None = None

    def get_all_skills(self) -> dict[str, Skill]:
        """Return all skills mapped by name."""
        return self._cache.skills

    def _get_skill_data(self, skill_name: str):
        data = self.get_all_skills().get(skill_name)
        if data:
            return data
        return Skill(skill_name, 1, 0, 1)

    def get_level(self, skill_name: str) -> int:
        """Return the boosted level for a skill."""
        return self._get_skill_data(skill_name).boosted_level

    def get_real_level(self, skill_name: str) -> int:
        """Return the real (unboosted) level for a skill."""
        return self._get_skill_data(skill_name).level

    def get_experience(self, skill_name: str) -> int:
        """Return the experience for a skill."""
        return self._get_skill_data(skill_name).xp

    def get_total_level(self) -> int:
        """Return the sum of all real skill levels."""
        skills_data = self._cache.skills
        return sum(data.level for data in skills_data.values())

    def get_total_experience(self) -> int:
        """Return the sum of all skill experience."""
        skills_data = self._cache.skills
        return sum(data.xp for data in skills_data.values())

    def gained_xp(self) -> bool:
        """Check if total experience increased since last call."""
        current_xp = self.get_total_experience()

        if self._last_total_xp is None:
            self._last_total_xp = current_xp
            return False

        if current_xp > self._last_total_xp:
            self._last_total_xp = current_xp
            return True

        return False

    def wait_xp(self, timeout: float = 5.0) -> bool:
        """Block until experience is gained or timeout expires."""
        if self._last_total_xp is None:
            self._last_total_xp = self.get_total_experience()

        if self.gained_xp():
            return True

        wait_until(lambda: self.gained_xp(), timeout=timeout, poll_interval=0.02)
        return False
