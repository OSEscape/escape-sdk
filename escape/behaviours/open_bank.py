from __future__ import annotations

from typing import TYPE_CHECKING

from escape._logger import logger
from escape.behaviours.interact_object import InteractObject
from escape.bt.actions import Action, Status
from escape.navigation.click import Click

if TYPE_CHECKING:
    from escape.pathfinder import PathfinderConfig
    from escape.walker import Walker


def _try_open_bank() -> bool:
    from escape.npcs import Npcs
    from escape.objects import Objects

    objects = Objects()
    obj = objects.nearest(options=["Bank"])
    if obj is not None and obj.interact("Bank"):
        return True
    npcs = Npcs()
    npc = npcs.nearest(actions=["Bank"])
    if npc is not None and npc.interact("Bank"):
        return True
    for obj in objects.get(option=["Use"]):
        if "bank" in obj.name.lower() and obj.interact("Use"):
            return True
    logger.debug("open_bank: no bank object or NPC found")
    return False


def _is_bank_open() -> bool:
    from escape.bank import Bank

    return Bank().is_open()


class OpenBank(Action):
    """BT action: navigate to nearest bank and open it."""

    def __init__(
        self,
        walker: Walker,
        config: PathfinderConfig | None = None,
        name: str = "OpenBank",
    ) -> None:
        super().__init__(name=name)
        self._walker = walker
        self._config = config
        self._interact: InteractObject | None = None
        self._click: Click | None = None

    def initialise(self) -> None:
        from escape.pathfinder import Pathfinder

        pf = Pathfinder()
        path = pf.find_nearest_bank(config=self._config)
        if not path.found:
            self._interact = None
            self._click = None
            return
        if path.is_empty():
            # Already at bank — just try clicking, no navigation needed
            self._interact = None
            self._click = Click(
                click=_try_open_bank,
                is_complete=_is_bank_open,
                timeout_ticks=10,
                name="open-bank",
            )
            return

        dest = path.tile_path[-1]
        self._interact = InteractObject(
            dest,
            self._walker,
            click=_try_open_bank,
            is_complete=_is_bank_open,
            timeout_ticks=10,
            config=self._config,
            name="open-bank",
        )
        self._interact.initialise()

    def update(self) -> Status:
        if _is_bank_open():
            return Status.SUCCESS
        if self._click is not None:
            return self._click.tick()
        if self._interact is None:
            logger.debug("open_bank: no path to bank")
            return Status.FAILURE
        return self._interact.update()

    def terminate(self, new_status: Status) -> None:
        if self._interact is not None:
            self._interact.terminate(new_status)
            self._interact = None
        if self._click is not None:
            self._click.reset()
            self._click = None
