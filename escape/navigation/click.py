from __future__ import annotations

from collections.abc import Callable

from escape._logger import logger
from escape.bt.actions import Status


class Click:
    """Click-and-wait state machine.

    Attempts to click, then waits for a completion condition or timeout.
    If the click fails it retries on subsequent ticks up to ``max_attempts``.
    If the click lands but the completion condition isn't met within
    ``timeout_ticks`` game ticks, the click is retried (counts as a new attempt).
    Framework-agnostic — usable from BT nodes, solvers, or direct loops.
    """

    def __init__(
        self,
        click: Callable[[], bool],
        is_complete: Callable[[], bool],
        timeout_ticks: int = 10,
        max_attempts: int = 3,
        name: str = "click",
    ) -> None:
        self._click_fn = click
        self._is_complete = is_complete
        self._timeout_ticks = timeout_ticks
        self._max_attempts = max_attempts
        self._name = name
        self._clicked = False
        self._click_tick: int | None = None
        self._attempts = 0

    @staticmethod
    def _game_tick() -> int | None:
        from escape._services import Services

        return Services.get().cache.tick

    def tick(self) -> Status:
        if self._is_complete():
            return Status.SUCCESS

        if not self._clicked:
            if not self._click_fn():
                self._attempts += 1
                if self._attempts >= self._max_attempts:
                    logger.debug("{}: click failed after {} attempts", self._name, self._attempts)
                    return Status.FAILURE
                logger.debug("{}: click missed, retrying ({}/{})", self._name, self._attempts, self._max_attempts)
                return Status.RUNNING
            self._clicked = True
            self._click_tick = self._game_tick()
            self._attempts += 1
            return Status.RUNNING

        current = self._game_tick()
        if current is not None and self._click_tick is not None:
            elapsed = current - self._click_tick
            if elapsed > self._timeout_ticks:
                if self._attempts >= self._max_attempts:
                    logger.debug("{}: timed out after {} game ticks ({} attempts exhausted)", self._name, elapsed, self._attempts)
                    return Status.FAILURE
                logger.debug("{}: timed out after {} game ticks, re-clicking ({}/{})", self._name, elapsed, self._attempts, self._max_attempts)
                self._clicked = False
                self._click_tick = None
                return Status.RUNNING

        return Status.RUNNING

    @property
    def clicked(self) -> bool:
        return self._clicked

    def reset(self) -> None:
        self._clicked = False
        self._click_tick = None
        self._attempts = 0
