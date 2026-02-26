from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape import Client
    from escape.htn.domain import Domain


def register_equipment(
    domain: Domain, c: Client, item_id: int, equip_action: str = "Wield"
) -> None:
    def plan_equip_item(state):
        if not state.has_item:
            return None
        state.equipped = True
        state.has_item = False
        return state

    domain.declare_actions({"equip_item": plan_equip_item})

    def m_already_equipped(state):
        if state.equipped:
            return []
        return None

    def m_from_inventory(state):
        return [("equip_item",)]

    domain.declare_tasks("equip", [m_already_equipped, m_from_inventory])

    def equip_item():
        return c.inventory.interact_item(item_id, equip_action)

    domain.declare_executors({"equip_item": equip_item})
