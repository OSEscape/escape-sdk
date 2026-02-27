from __future__ import annotations

from typing import TYPE_CHECKING

from escape.bt.actions import Action, Status
from escape.navigation.navigator import Navigator

if TYPE_CHECKING:
    from escape.pathfinder import PathfinderConfig
    from escape.point import Point
    from escape.walker import Walker


class NavigateTo(Action):
    """BT Action that navigates the player to a destination.

    Thin wrapper around :class:`Navigator` for use in behaviour trees.
    """

    def __init__(
        self,
        dest: Point,
        walker: Walker,
        config: PathfinderConfig | None = None,
        arrival_threshold: int = 2,
        name: str = "NavigateTo",
    ) -> None:
        super().__init__(name=name)
        if walker._registry is None:
            raise RuntimeError("Walker has no solver registry — pass one to Walker() or use Client")
        self._nav = Navigator(
            dest,
            walker,
            walker._pathfinder,
            walker._registry,
            config,
            arrival_threshold,
        )

    def initialise(self) -> None:
        self._nav.reset()

    def update(self) -> Status:
        return self._nav.tick()

    def terminate(self, new_status: Status) -> None:
        self._nav.reset()
