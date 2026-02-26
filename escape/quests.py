from escape._resources import varps
from escape._resources.questdata import ALL_QUESTS, Quest
from escape.constants import VarPlayerID
from escape.gametab import GameTab, GameTabs


class Quests(GameTabs):
    TAB_TYPE = GameTab.PROGRESS

    def __init__(self):
        super().__init__()

    @property
    def total_quest_points(self) -> int | None:
        return varps.get_varp_value(VarPlayerID.QP)

    def is_quest_completed(self, quest: Quest) -> bool | None:
        state = self.get_quest_state(quest)
        if state is None:
            return None
        return state >= quest.end_state

    def is_quest_started(self, quest: Quest) -> bool | None:
        state = self.get_quest_state(quest)
        if state is None:
            return None
        return state > quest.unstarted_state

    def get_quest_state(self, quest: Quest) -> int | None:
        if quest.varbit is not None:
            return varps.get_varbit(quest.varbit)

        if quest.varp is not None:
            return varps.get_varp_value(quest.varp)
        return None

    def get_all_quests(self) -> dict[str, Quest]:
        result = {}
        for q in ALL_QUESTS:
            result[q.name] = q

        return result

    def is_quest_f2p(self, quest: Quest) -> bool:
        return not quest.members

    def is_miniquest(self, quest: Quest) -> bool:
        return quest.miniquest
