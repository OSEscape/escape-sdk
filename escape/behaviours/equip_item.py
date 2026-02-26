"""Generic equip-from-inventory behaviour."""

from __future__ import annotations

from typing import TYPE_CHECKING

from escape.behaviours.interact_inventory import InteractInventory

if TYPE_CHECKING:
    from escape._models import ItemIdentifier


def EquipItem(  # noqa: N802
    identifier: ItemIdentifier | list[ItemIdentifier],
    option: str = "Wear",
    timeout_ticks: int = 5,
    name: str = "EquipItem",
) -> InteractInventory:
    """Equip an item from inventory and wait for it to appear in equipment.

    Convenience wrapper around :class:`InteractInventory` with a completion
    check that polls the equipment container.
    """
    ids = identifier if isinstance(identifier, list) else [identifier]

    def _equipped() -> bool:
        from escape.equipment import Equipment

        equip = Equipment()
        return any(equip.contains(i) for i in ids)

    return InteractInventory(
        identifier=identifier,
        option=option,
        is_complete=_equipped,
        timeout_ticks=timeout_ticks,
        name=name,
    )
