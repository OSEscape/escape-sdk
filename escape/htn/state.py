from __future__ import annotations

from copy import deepcopy
from typing import Any


class State:
    def __init__(self, name: str) -> None:
        self.name = name

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def update(self, state: State) -> State:
        self.__dict__.update(state.__dict__)
        return self

    def copy(self) -> State:
        return deepcopy(self)


class MultiGoal:
    def __init__(self, name: str, goal_tag: str | None = None) -> None:
        self.name = name
        self.goal_tag = goal_tag

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def update(self, multigoal: MultiGoal) -> MultiGoal:
        self.__dict__.update(multigoal.__dict__)
        return self

    def copy(self) -> MultiGoal:
        return deepcopy(self)


def goals_not_achieved(state: State, multigoal: MultiGoal) -> dict[str, dict[str, Any]]:
    unachieved: dict[str, dict[str, Any]] = {}
    for attr_name in vars(multigoal):
        if attr_name in ("name", "goal_tag"):
            continue
        goal_bindings = vars(multigoal).get(attr_name)
        state_bindings = vars(state).get(attr_name)
        if goal_bindings is None or state_bindings is None:
            continue
        for arg, val in goal_bindings.items():
            if state_bindings.get(arg) != val:
                if attr_name not in unachieved:
                    unachieved[attr_name] = {}
                unachieved[attr_name][arg] = val
    return unachieved
