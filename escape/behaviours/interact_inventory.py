"""Generic interact-with-inventory-item behaviour."""

from __future__ import annotations

from typing import TYPE_CHECKING

from escape.bt.actions import Action, Status

if TYPE_CHECKING:
    from collections.abc import Callable

    from escape._models import ItemIdentifier


class InteractInventory(Action):
    """Interact with an inventory item and wait for a completion condition.

    Two-phase tick-based state machine: INTERACT → WAIT.
    Returns SUCCESS immediately if ``is_complete`` is already satisfied.
    Accepts a single ID or a list of IDs (interacts with first found).
    """

    _INTERACT = 0
    _WAIT = 1

    def __init__(
        self,
        identifier: ItemIdentifier | list[ItemIdentifier],
        option: str,
        is_complete: Callable[[], bool],
        timeout_ticks: int = 5,
        name: str = "InteractInventory",
    ) -> None:
        super().__init__(name=name)
        self._ids = identifier if isinstance(identifier, list) else [identifier]
        self._option = option
        self._is_complete = is_complete
        self._timeout_ticks = timeout_ticks
        self._phase = self._INTERACT
        self._deadline = 0

    def initialise(self) -> None:
        self._phase = self._INTERACT
        self._deadline = 0

    def update(self) -> Status:
        from escape._services import Services
        from escape.inventory import Inventory

        if self._is_complete():
            return Status.SUCCESS

        cache = Services.get().cache
        tick = cache.tick or 0

        if self._phase == self._INTERACT:
            inv = Inventory()
            for id in self._ids:
                if inv.contains(id) and inv.interact_item(id, option=self._option):
                    self._phase = self._WAIT
                    self._deadline = tick + self._timeout_ticks
                    return Status.RUNNING
            return Status.FAILURE

        if self._phase == self._WAIT:
            if tick >= self._deadline:
                return Status.FAILURE
            return Status.RUNNING

        return Status.FAILURE
