from __future__ import annotations

from escape.htn.actions import ActionFunc, Actions, ExecutorFunc
from escape.htn.methods import MethodFunc, Methods


class Domain:
    def __init__(self, name: str) -> None:
        self.name = name
        self.methods = Methods()
        self.actions = Actions()

    def declare_actions(self, actions: list[ActionFunc] | dict[str, ActionFunc]) -> None:
        self.actions.declare_actions(actions)

    def declare_executors(self, executor_map: dict[str, ExecutorFunc]) -> None:
        self.actions.declare_executors(executor_map)

    def declare_tasks(self, task_name: str, method_list: list[MethodFunc]) -> None:
        self.methods.declare_tasks(task_name, method_list)

    def declare_goals(self, goal_name: str, method_list: list[MethodFunc]) -> None:
        self.methods.declare_goals(goal_name, method_list)

    def declare_multigoals(self, tag: str | None, method_list: list[MethodFunc]) -> None:
        self.methods.declare_multigoals(tag, method_list)
