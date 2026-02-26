"""Generic interact-with-equipment-slot behaviour."""

from __future__ import annotations

from typing import TYPE_CHECKING

from escape.bt.actions import Action, Status

if TYPE_CHECKING:
    from collections.abc import Callable

    from escape.equipment import EquipmentSlots


class InteractEquipment(Action):
    """Interact with an equipment slot and wait for a completion condition.

    Two-phase tick-based state machine: INTERACT → WAIT.
    Returns SUCCESS immediately if ``is_complete`` is already satisfied.
    """

    _INTERACT = 0
    _WAIT = 1

    def __init__(
        self,
        slot: EquipmentSlots,
        option: str,
        is_complete: Callable[[], bool],
        timeout_ticks: int = 10,
        name: str = "InteractEquipment",
    ) -> None:
        super().__init__(name=name)
        self._slot = slot
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
        from escape.equipment import Equipment

        if self._is_complete():
            return Status.SUCCESS

        cache = Services.get().cache
        tick = cache.tick or 0

        if self._phase == self._INTERACT:
            equip = Equipment()
            if equip.interact_slot(self._slot, option=self._option):
                self._phase = self._WAIT
                self._deadline = tick + self._timeout_ticks
                return Status.RUNNING
            return Status.FAILURE

        if self._phase == self._WAIT:
            if tick >= self._deadline:
                return Status.FAILURE
            return Status.RUNNING

        return Status.FAILURE
