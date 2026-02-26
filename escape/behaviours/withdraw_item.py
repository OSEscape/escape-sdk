"""Generic withdraw-from-bank behaviour."""

from __future__ import annotations

from escape._models import ItemIdentifier
from escape.bt.actions import Action, Status


class WithdrawItem(Action):
    """Withdraw an item from the bank and wait for it to appear in inventory.

    Two-phase tick-based state machine: WITHDRAW → WAIT.
    Returns SUCCESS immediately if the item is already in inventory.
    Accepts a single ID or a list of IDs (tries first available).
    """

    _WITHDRAW = 0
    _WAIT = 1

    def __init__(
        self,
        identifier: ItemIdentifier | list[ItemIdentifier],
        quantity: int = 1,
        timeout_ticks: int = 5,
        name: str = "WithdrawItem",
    ) -> None:
        super().__init__(name=name)
        self._ids = identifier if isinstance(identifier, list) else [identifier]
        self._quantity = quantity
        self._timeout_ticks = timeout_ticks
        self._phase = self._WITHDRAW
        self._deadline = 0

    def initialise(self) -> None:
        self._phase = self._WITHDRAW
        self._deadline = 0

    def _has_any(self, container) -> bool:
        return any(container.contains(id) for id in self._ids)

    def update(self) -> Status:
        from escape._services import Services
        from escape.bank import Bank
        from escape.inventory import Inventory

        inv = Inventory()
        if self._has_any(inv):
            return Status.SUCCESS

        cache = Services.get().cache
        tick = cache.tick or 0

        if self._phase == self._WITHDRAW:
            bank = Bank()
            withdrawn = False
            for id in self._ids:
                if bank.contains(id):
                    if bank.withdraw(id, quantity=self._quantity):
                        withdrawn = True
                        break
            if not withdrawn:
                return Status.FAILURE
            self._phase = self._WAIT
            self._deadline = tick + self._timeout_ticks
            return Status.RUNNING

        if self._phase == self._WAIT:
            if self._has_any(inv):
                return Status.SUCCESS
            if tick >= self._deadline:
                return Status.FAILURE
            return Status.RUNNING

        return Status.FAILURE
