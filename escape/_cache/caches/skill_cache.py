from __future__ import annotations

from typing import TYPE_CHECKING

from escape._models import Skill

if TYPE_CHECKING:
    from escape._proto.bridge.v1.bridge_pb2 import (  # pyright: ignore[reportMissingImports]
        StatChanged,
        StatsSnapshot,
    )


class SkillCache:
    def __init__(self):
        self.skills: dict[str, Skill] = {}

    def set_skill(self, skill_name: str, level: int, xp: int, boosted: int) -> None:
        self.skills[skill_name] = Skill(skill_name, level, xp, boosted)

    def get_skill(self, skill_name: str) -> Skill | None:
        return self.skills.get(skill_name)

    def process_snapshot(self, snapshot: StatsSnapshot) -> None:
        for stat in snapshot.stats:
            self.set_skill(stat.skill, stat.level, stat.xp, stat.boosted_level)

    def process_change(self, change: StatChanged) -> None:
        stat = change.stat
        self.set_skill(stat.skill, stat.level, stat.xp, stat.boosted_level)
