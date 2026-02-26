from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape.htn.state import State

ActionFunc = Callable[..., "State | None"]
ExecutorFunc = Callable[..., bool]


class Actions:
    def __init__(self) -> None:
        self.action_dict: dict[str, ActionFunc] = {}
        self.executor_dict: dict[str, ExecutorFunc] = {}

    def declare_actions(self, actions: list[ActionFunc] | dict[str, ActionFunc]) -> None:
        if isinstance(actions, dict):
            self.action_dict.update(actions)
        else:
            self.action_dict.update({action.__name__: action for action in actions})

    def declare_executors(self, executor_map: dict[str, ExecutorFunc]) -> None:
        self.executor_dict.update(executor_map)
