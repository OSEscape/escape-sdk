from __future__ import annotations

from typing import TYPE_CHECKING

from escape._logger import logger
from escape.bt.actions import Status
from escape.navigation.click import Click
from escape.navigation.navigator import Navigator

if TYPE_CHECKING:
    from escape.navigation.registry import SolverRegistry
    from escape.pathfinder import Pathfinder, PathfinderConfig
    from escape.walker import Walker


class OpenBank:
    """Navigate to nearest bank and open it.

    Two-phase tick-based state machine:
      1. Navigate to the nearest bank using the global pathfinder.
      2. Click the bank object/NPC to open the interface.
    """

    def __init__(
        self,
        walker: Walker,
        pathfinder: Pathfinder,
        registry: SolverRegistry,
        config: PathfinderConfig | None = None,
    ) -> None:
        self._walker = walker
        self._pathfinder = pathfinder
        self._registry = registry
        self._config = config

        self._navigator: Navigator | None = None
        self._click: Click | None = None

    def reset(self) -> None:
        if self._navigator is not None:
            self._navigator.reset()
        self._navigator = None
        self._click = None

    def _is_bank_open(self) -> bool:
        from escape.bank import Bank

        return Bank().is_open()

    def tick(self) -> Status:
        if self._is_bank_open():
            return Status.SUCCESS

        # Phase 2: interact (already navigated)
        if self._click is not None:
            return self._click.tick()

        # Phase 1: navigate
        return self._tick_navigate()

    def _tick_navigate(self) -> Status:
        if self._navigator is None:
            path = self._pathfinder.find_nearest_bank(config=self._config)
            if not path.found:
                logger.debug("open_bank: no path to bank")
                return Status.FAILURE
            if path.is_empty():
                # Already at bank — skip navigation, go straight to interact
                self._click = Click(
                    click=self._try_open_bank,
                    is_complete=self._is_bank_open,
                    timeout_ticks=10,
                    name="open-bank",
                )
                return Status.RUNNING
            dest = path.tile_path[-1]
            self._navigator = Navigator(
                dest,
                self._walker,
                self._pathfinder,
                self._registry,
                self._config,
            )

        result = self._navigator.tick()
        if result == Status.SUCCESS:
            # Arrived — transition to interact phase
            self._click = Click(
                click=self._try_open_bank,
                is_complete=self._is_bank_open,
                timeout_ticks=10,
                name="open-bank",
            )
            return Status.RUNNING
        return result

    def _try_open_bank(self) -> bool:
        from escape.npcs import Npcs
        from escape.objects import Objects

        objects = Objects()
        # Bank booths, most bank chests — "Bank" action
        obj = objects.nearest(options=["Bank"])
        if obj is not None and obj.interact("Bank"):
            return True
        # Banker NPCs, GE clerks
        npcs = Npcs()
        npc = npcs.nearest(actions=["Bank"])
        if npc is not None and npc.interact("Bank"):
            return True
        # Bank chests with "Use" only — name must contain "bank"
        for obj in objects.get(option=["Use"]):
            if "bank" in obj.name.lower() and obj.interact("Use"):
                return True
        logger.debug("open_bank: no bank object or NPC found nearby")
        return False
