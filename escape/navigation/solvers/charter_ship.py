from __future__ import annotations

from typing import TYPE_CHECKING

import escape.timing as timing
from escape._logger import logger
from escape.bt.actions import Status
from escape.navigation.click import Click
from escape.navigation.solvers.npc_click import _parse_npc_metadata
from escape.point import Point

if TYPE_CHECKING:
    from escape.pathfinder import Transport


class CharterShipSolver:
    """Transport solver: click charter NPC, select destination from interface."""

    def __init__(self) -> None:
        self._clicker: Click | None = None

    def reset(self) -> None:
        if self._clicker is not None:
            self._clicker.reset()
        self._clicker = None

    def solve(self, transport: Transport) -> Status:
        if self._clicker is None:
            action, name, npc_id = _parse_npc_metadata(transport)
            destination = transport.name

            def use_charter() -> bool:
                from escape.interfaces import Interfaces
                from escape.npcs import Npcs

                npcs = Npcs()
                actions = [action] if action else None

                # Click the charter NPC
                clicked = False
                npc = None
                if npc_id is not None:
                    npc = npcs.nearest(ids=[npc_id], actions=actions)
                    if npc is None and name is not None:
                        npc = npcs.nearest(names=[name], actions=actions)
                elif name is not None:
                    npc = npcs.nearest(names=[name], actions=actions)
                if npc is not None:
                    clicked = npc.interact(action)

                if not clicked:
                    logger.debug("charter-solver: failed to click NPC")
                    return False

                # Wait for chartering interface
                charter = Interfaces().charter_ship
                if not timing.wait_until(charter.is_open, timeout=5):
                    logger.debug("charter-solver: interface did not open")
                    return False

                # Select destination
                logger.debug("charter-solver: selecting '{}'", destination)
                return charter.interact(destination)

            duration = transport.metadata[0].duration_ticks if transport.metadata else 0
            self._clicker = Click(
                click=use_charter,
                is_complete=lambda: self._near_destination(transport),
                timeout_ticks=3 + duration,
                name=f"charter-{destination}",
            )

        return self._clicker.tick()

    def _near_destination(self, transport: Transport) -> bool:
        from escape._services import Services

        cache = Services.get().cache
        pos = cache.world_position
        return pos is not None and transport.destination.is_nearby(Point(*pos), 10)
