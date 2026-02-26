from __future__ import annotations

from typing import TYPE_CHECKING

from escape.htn.methods import split_multigoal
from escape.timing import wait_until

if TYPE_CHECKING:
    from escape import Client
    from escape.htn.domain import Domain


def register_banking(domain: Domain, c: Client, items: dict[str, int]) -> None:
    def plan_open_bank(state):
        state.bank_open = True
        return state

    def plan_withdraw_item(state, item):
        if not state.bank_open:
            return None
        state.has[item] = True
        return state

    def plan_close_bank(state):
        state.bank_open = False
        return state

    domain.declare_actions(
        {
            "open_bank": plan_open_bank,
            "withdraw_item": plan_withdraw_item,
            "close_bank": plan_close_bank,
        }
    )

    def m_bank_already_open(state, item):
        if state.bank_open:
            return [("withdraw_item", item)]
        return None

    def m_open_then_withdraw(state, item):
        return [("open_bank",), ("withdraw_item", item)]

    def m_already_have(state, item, desired):
        if state.has[item] == desired:
            return []
        return None

    def m_withdraw(state, item, desired):
        return [("withdraw", item)]

    domain.declare_tasks("withdraw", [m_bank_already_open, m_open_then_withdraw])
    domain.declare_goals("has", [m_already_have, m_withdraw])
    domain.declare_multigoals(None, [split_multigoal])

    def open_bank():
        obj = c.objects.nearest(names=["Bank booth"], options=["Bank"])
        if obj is None or not obj.interact("Bank"):
            return False
        return wait_until(c.bank.is_open, timeout=5.0)

    def withdraw_item(item):
        return c.bank.withdraw(items[item], quantity=1)

    def close_bank():
        return c.bank.close()

    domain.declare_executors(
        {
            "open_bank": open_bank,
            "withdraw_item": withdraw_item,
            "close_bank": close_bank,
        }
    )
