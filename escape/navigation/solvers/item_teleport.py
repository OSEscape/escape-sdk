from __future__ import annotations

from typing import TYPE_CHECKING

from escape._logger import logger
from escape.bt.actions import Status
from escape.navigation.click import Click
from escape.navigation.solvers.item_data import lookup_item_teleport
from escape.point import Point

if TYPE_CHECKING:
    from escape.pathfinder import Transport


class ItemTeleportSolver:
    """Transport solver: use a teleport item (jewelry, tablet, diary item, etc.)."""

    def __init__(self) -> None:
        self._clicker: Click | None = None

    def reset(self) -> None:
        if self._clicker is not None:
            self._clicker.reset()
        self._clicker = None

    def solve(self, transport: Transport) -> Status:
        if self._clicker is None:
            info = lookup_item_teleport(transport.name)
            if info is None:
                logger.warning("item-solver: unknown item teleport '{}'", transport.name)
                return Status.FAILURE

            # Extract alternative item IDs from transport metadata.
            item_ids: list[int] = []
            if transport.metadata:
                item_ids = transport.metadata[0].item_requirements

            def use_item() -> bool:
                from escape.equipment import Equipment
                from escape.inventory import Inventory

                # Try equipment first (no tab-switching needed).
                equipment = Equipment()
                for item_id in item_ids:
                    if equipment.find_slot(item_id) is not None:
                        logger.debug(
                            "item-solver: using equipped item {} option='{}'",
                            item_id,
                            info.option,
                        )
                        return equipment.interact_item(item_id, option=info.option)

                # Fall back to inventory.
                inventory = Inventory()
                for item_id in item_ids:
                    if inventory.find_slot(item_id) is not None:
                        logger.debug(
                            "item-solver: using inventory item {} option='{}'",
                            item_id,
                            info.option,
                        )
                        return inventory.interact_item(item_id, option=info.option)

                logger.warning("item-solver: none of item IDs {} found", item_ids)
                return False

            duration = transport.metadata[0].duration_ticks if transport.metadata else 0
            self._clicker = Click(
                click=use_item,
                is_complete=lambda: self._near_destination(transport),
                timeout_ticks=3 + duration,
                name=f"item-{transport.name}",
            )

        return self._clicker.tick()

    def _near_destination(self, transport: Transport) -> bool:
        from escape._services import Services

        cache = Services.get().cache
        pos = cache.world_position
        return pos is not None and transport.destination.is_nearby(Point(*pos), 5)
