"""Rune pouch contents via varbit lookup."""

from __future__ import annotations

from escape._models import Item
from escape._resources import varps
from escape.constants import ItemID, VarbitID

# Varbit type index -> (item_id, name)
RUNE_POUCH_RUNES: dict[int, tuple[int, str]] = {
    1: (ItemID.AIRRUNE, "Air rune"),
    2: (ItemID.WATERRUNE, "Water rune"),
    3: (ItemID.EARTHRUNE, "Earth rune"),
    4: (ItemID.FIRERUNE, "Fire rune"),
    5: (ItemID.MINDRUNE, "Mind rune"),
    6: (ItemID.CHAOSRUNE, "Chaos rune"),
    7: (ItemID.DEATHRUNE, "Death rune"),
    8: (ItemID.BLOODRUNE, "Blood rune"),
    9: (ItemID.COSMICRUNE, "Cosmic rune"),
    10: (ItemID.NATURERUNE, "Nature rune"),
    11: (ItemID.LAWRUNE, "Law rune"),
    12: (ItemID.BODYRUNE, "Body rune"),
    13: (ItemID.SOULRUNE, "Soul rune"),
    14: (ItemID.ASTRALRUNE, "Astral rune"),
    15: (ItemID.MISTRUNE, "Mist rune"),
    16: (ItemID.MUDRUNE, "Mud rune"),
    17: (ItemID.DUSTRUNE, "Dust rune"),
    18: (ItemID.LAVARUNE, "Lava rune"),
    19: (ItemID.STEAMRUNE, "Steam rune"),
    20: (ItemID.SMOKERUNE, "Smoke rune"),
    21: (ItemID.WRATHRUNE, "Wrath rune"),
    22: (ItemID.SUNFIRERUNE, "Sunfire rune"),
    23: (ItemID.AETHERRUNE, "Aether rune"),
}

_TYPE_VARBITS: tuple[int, ...] = (
    VarbitID.RUNE_POUCH_TYPE_1,
    VarbitID.RUNE_POUCH_TYPE_2,
    VarbitID.RUNE_POUCH_TYPE_3,
    VarbitID.RUNE_POUCH_TYPE_4,
    VarbitID.RUNE_POUCH_TYPE_5,
    VarbitID.RUNE_POUCH_TYPE_6,
)

_QTY_VARBITS: tuple[int, ...] = (
    VarbitID.RUNE_POUCH_QUANTITY_1,
    VarbitID.RUNE_POUCH_QUANTITY_2,
    VarbitID.RUNE_POUCH_QUANTITY_3,
    VarbitID.RUNE_POUCH_QUANTITY_4,
    VarbitID.RUNE_POUCH_QUANTITY_5,
    VarbitID.RUNE_POUCH_QUANTITY_6,
)


def get_rune_pouch_items() -> list[Item]:
    """Read rune pouch contents from varbits, returning Item objects."""
    items: list[Item] = []
    for type_vb, qty_vb in zip(_TYPE_VARBITS, _QTY_VARBITS, strict=True):
        type_idx = varps.get_varbit(type_vb)
        if not type_idx:
            continue
        qty = varps.get_varbit(qty_vb)
        if not qty:
            continue
        rune = RUNE_POUCH_RUNES.get(type_idx)
        if rune is not None:
            items.append(Item(id=rune[0], name=rune[1], quantity=qty, noted=False))
    return items


RUNE_POUCH_IDS: frozenset[int] = frozenset(
    (
        ItemID.BH_RUNE_POUCH,
        ItemID.BH_RUNE_POUCH_TROUVER,
        ItemID.DIVINE_RUNE_POUCH,
        ItemID.DIVINE_RUNE_POUCH_TROUVER,
    )
)


def get_rune_pouch_quantity_by_id() -> dict[int, int]:
    """Read rune pouch contents as {item_id: quantity} dict for pathfinding."""
    result: dict[int, int] = {}
    for type_vb, qty_vb in zip(_TYPE_VARBITS, _QTY_VARBITS, strict=True):
        type_idx = varps.get_varbit(type_vb)
        if not type_idx:
            continue
        qty = varps.get_varbit(qty_vb)
        if not qty:
            continue
        rune = RUNE_POUCH_RUNES.get(type_idx)
        if rune is not None:
            result[rune[0]] = result.get(rune[0], 0) + qty
    return result


def inventory_rune_pouch(inventory: dict[int, int]) -> dict[int, int]:
    """Return rune pouch contents if a rune pouch is in inventory, else empty dict."""
    if not any(item_id in inventory for item_id in RUNE_POUCH_IDS):
        return {}
    return get_rune_pouch_quantity_by_id()


def bank_rune_pouch(bank: dict[int, int] | None) -> dict[int, int]:
    """Return rune pouch contents if a rune pouch is in the bank, else empty dict."""
    if bank is None:
        return {}
    if not any(item_id in bank for item_id in RUNE_POUCH_IDS):
        return {}
    return get_rune_pouch_quantity_by_id()


class RunePouch:
    """Rune pouch accessor backed by live cache."""

    @property
    def items(self) -> list[Item]:
        """Get rune pouch contents as Item objects."""
        return get_rune_pouch_items()

    @property
    def quantity_by_id(self) -> dict[int, int]:
        """Get rune pouch contents as {item_id: quantity} dict."""
        return get_rune_pouch_quantity_by_id()

    def __repr__(self) -> str:
        runes = self.items
        if not runes:
            return "RunePouch(empty)"
        contents = ", ".join(f"{r.name} x{r.quantity}" for r in runes)
        return f"RunePouch({contents})"
