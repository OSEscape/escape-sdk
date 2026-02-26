from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from escape.htn.state import MultiGoal, State

MethodFunc = Callable[..., "Sequence[tuple[Any, ...] | MultiGoal] | None"]


class Methods:
    def __init__(self) -> None:
        self.tasks: dict[str, list[MethodFunc]] = {}
        self.goals: dict[str, list[MethodFunc]] = {}
        self.multigoals: dict[str | None, list[MethodFunc]] = {None: []}

    def declare_tasks(self, task_name: str, method_list: list[MethodFunc]) -> None:
        assert isinstance(task_name, str)
        assert isinstance(method_list, list)
        for method in method_list:
            assert callable(method)
        self.tasks[task_name] = method_list

    def declare_goals(self, goal_name: str, method_list: list[MethodFunc]) -> None:
        assert isinstance(goal_name, str)
        assert isinstance(method_list, list)
        for method in method_list:
            assert callable(method)
        self.goals[goal_name] = method_list

    def declare_multigoals(self, multigoal_tag: str | None, method_list: list[MethodFunc]) -> None:
        assert isinstance(multigoal_tag, (str, type(None)))
        assert isinstance(method_list, list)
        for method in method_list:
            assert callable(method)
        self.multigoals[multigoal_tag] = method_list


def split_multigoal(state: State, multigoal: MultiGoal) -> list[Any]:
    from escape.htn.state import goals_not_achieved

    goal_dict = goals_not_achieved(state, multigoal)
    goal_list: list[Any] = []
    for state_var_name in goal_dict:
        for arg in goal_dict[state_var_name]:
            val = goal_dict[state_var_name][arg]
            goal_list.append((state_var_name, arg, val))
    if goal_list:
        return [*goal_list, multigoal]
    return goal_list
