from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from escape.bt.actions import Action, Status
from escape.navigation.click import Click
from escape.navigation.navigator import Navigator

if TYPE_CHECKING:
    from escape.pathfinder import PathfinderConfig
    from escape.point import Point
    from escape.walker import Walker


class InteractObject(Action):
    """Navigate toward a destination and click to interact.

    Tries to click early whenever the destination tile is visible on screen.
    Once clicked, waits for the completion condition or timeout.
    """

    def __init__(
        self,
        dest: Point,
        walker: Walker,
        click: Callable[[], bool],
        is_complete: Callable[[], bool],
        timeout_ticks: int = 10,
        config: PathfinderConfig | None = None,
        arrival_threshold: int = 2,
        name: str = "InteractObject",
    ) -> None:
        super().__init__(name=name)
        if walker._registry is None:
            raise RuntimeError("Walker has no solver registry — pass one to Walker() or use Client")
        self._dest = dest
        self._scene = walker._scene
        self._nav = Navigator(
            dest,
            walker,
            walker._pathfinder,
            walker._registry,
            config,
            arrival_threshold,
        )
        self._click = Click(
            click=click,
            is_complete=is_complete,
            timeout_ticks=timeout_ticks,
            name=name,
        )

    def initialise(self) -> None:
        self._nav.reset()
        self._click.reset()

    def update(self) -> Status:
        # After a successful click, just wait for completion
        if self._click.clicked:
            return self._click.tick()

        # Try clicking early if destination tile is visible
        if self._scene.is_tile_on_screen(self._dest.x, self._dest.y):
            self.logger.debug("Destination tile is on screen, attempting early click")
            result = self._click.tick()
            if result != Status.FAILURE:
                return result
            self._click.reset()

        # Walk toward destination
        result = self._nav.tick()
        if result == Status.SUCCESS:
            return Status.RUNNING  # arrived, will click next tick
        return result

    def terminate(self, new_status: Status) -> None:
        self._nav.reset()
        self._click.reset()
