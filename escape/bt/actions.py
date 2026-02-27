from __future__ import annotations

from typing import TYPE_CHECKING, Any

import py_trees

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from escape.bt.context import Blackboard

Status = py_trees.common.Status


class Action(py_trees.behaviour.Behaviour):
    """Base behavior tree action node. Override update() to implement."""

    blackboard: Blackboard

    def __init__(self, name: str = "Action") -> None:
        super().__init__(name=name)

    def setup(self, **kwargs: object) -> None:
        if "blackboard" in kwargs:
            self.blackboard = kwargs["blackboard"]  # type: ignore[assignment]

    def tick(self) -> Iterator[py_trees.behaviour.Behaviour]:
        if self.status != Status.RUNNING:
            self.initialise()
        new_status = self.update()
        if new_status != Status.RUNNING:
            self.stop(new_status)
        self.status = new_status
        yield self


class Condition(Action):
    """Behavior tree condition that succeeds or fails based on check()."""

    def __init__(self, name: str = "Condition") -> None:
        super().__init__(name=name)

    def check(self) -> bool:
        """Evaluate the condition and return the result."""
        raise NotImplementedError

    def update(self) -> Status:
        """Tick this condition and return success or failure."""
        return Status.SUCCESS if self.check() else Status.FAILURE


class ForEach(py_trees.decorators.Decorator):
    """Decorator that iterates a child over a context collection."""

    blackboard: Blackboard

    def __init__(
        self,
        name: str,
        child: py_trees.behaviour.Behaviour,
        source_key: str,
        target_key: str,
    ) -> None:
        super().__init__(name=name, child=child)
        self.source_key = source_key
        self.target_key = target_key
        self._iterator: Iterator[Any] | None = None
        self._current_item: Any = None

    def setup(self, **kwargs: object) -> None:
        if "blackboard" in kwargs:
            self.blackboard = kwargs["blackboard"]  # type: ignore[assignment]

    def initialise(self) -> None:
        iterable = self.blackboard.get(self.source_key) or []
        self._iterator = iter(iterable)
        self._advance()

    def _advance(self) -> None:
        try:
            if self._iterator is not None:
                self._current_item = next(self._iterator)
                self.blackboard.set(self.target_key, self._current_item)
        except StopIteration:
            self._current_item = None

    def tick(self) -> Iterator[py_trees.behaviour.Behaviour]:
        """Tick the child for the current item in the iteration."""
        if self.status != Status.RUNNING:
            self.initialise()

        # Empty source - succeed immediately without ticking child
        if self._current_item is None:
            self.stop(Status.SUCCESS)
            self.status = Status.SUCCESS
            yield self
            return

        # Tick child and update
        yield from self.decorated.tick()
        new_status = self.update()
        if new_status != Status.RUNNING:
            self.stop(new_status)
        self.status = new_status
        yield self

    def update(self) -> Status:
        """Advance to the next item or propagate child status."""
        child_status = self.decorated.status

        if child_status == Status.SUCCESS:
            self._advance()
            if self._current_item is not None:
                return Status.RUNNING
            return Status.SUCCESS

        return child_status

    def terminate(self, new_status: Status) -> None:
        """Clear the iterator state."""
        self._iterator = None
        self._current_item = None


# ---------------------------------------------------------------------------
# Lightweight node factories
# ---------------------------------------------------------------------------


class _FnCondition(Condition):
    """Condition backed by a plain callable."""

    def __init__(self, name: str, fn: Callable[[], bool]) -> None:
        super().__init__(name=name)
        self._fn = fn

    def check(self) -> bool:
        return self._fn()


def condition_node(name: str, fn: Callable[[], bool]) -> Condition:
    """Create a Condition node from a ``() -> bool`` callable."""
    return _FnCondition(name=name, fn=fn)


class _FnAction(Action):
    """Single-tick action backed by a plain callable."""

    def __init__(self, name: str, fn: Callable[[], bool]) -> None:
        super().__init__(name=name)
        self._fn = fn

    def update(self) -> Status:
        return Status.SUCCESS if self._fn() else Status.FAILURE


def action_node(name: str, fn: Callable[[], bool]) -> Action:
    """Create a single-tick Action from a ``() -> bool`` callable."""
    return _FnAction(name=name, fn=fn)
