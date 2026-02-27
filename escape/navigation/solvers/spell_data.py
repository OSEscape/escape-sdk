"""Mapping from transport display_info names to spellbook widget IDs.

Manually maintained. Keys are the `display_info` strings from TELEPORTATION_SPELL
transports in the graph data. Values are (widget_id, option) tuples.

Variant spells (e.g. "Varrock Teleport: GE") share the same widget as the base
spell — the varbit determines the destination, not the click.

Some spell names appear on multiple spellbooks (e.g. "Ape Atoll Teleport" is on
both Standard and Arceuus). These are keyed by (name, spellbook_varbit_value)
in _AMBIGUOUS. The spellbook varbit is 4070.
"""

from __future__ import annotations

from dataclasses import dataclass

from escape.constants import InterfaceID, VarbitID

_S = InterfaceID.MagicSpellbook

SPELLBOOK_VARBIT = VarbitID.SPELLBOOK


@dataclass(frozen=True, slots=True)
class SpellInfo:
    widget_id: int
    option: str = "Cast"


# -- Standard spellbook (varbit 4070 == 0) ----------------------------------

_STANDARD: dict[str, SpellInfo] = {
    "Lumbridge Home Teleport": SpellInfo(_S.TELEPORT_HOME_STANDARD),
    "Varrock Teleport": SpellInfo(_S.VARROCK_TELEPORT),
    "Varrock Teleport: GE": SpellInfo(_S.VARROCK_TELEPORT, "Grand exchange"),
    "Lumbridge Teleport": SpellInfo(_S.LUMBRIDGE_TELEPORT),
    "Falador Teleport": SpellInfo(_S.FALADOR_TELEPORT),
    "Teleport to House": SpellInfo(_S.TELEPORT_TO_YOUR_HOUSE),
    "Camelot Teleport": SpellInfo(_S.CAMELOT_TELEPORT),
    "Ardougne Teleport": SpellInfo(_S.ARDOUGNE_TELEPORT),
    "Watchtower Teleport": SpellInfo(_S.WATCHTOWER_TELEPORT),
    "Watchtower Teleport: Yanille": SpellInfo(_S.WATCHTOWER_TELEPORT, "Yanille"),
    "Trollheim Teleport": SpellInfo(_S.TROLLHEIM_TELEPORT),
    "Kourend Castle Teleport": SpellInfo(_S.KOUREND_TELEPORT),
    "Civitas illa Fortis Teleport": SpellInfo(_S.FORTIS_TELEPORT),
}

# -- Ancient spellbook (varbit 4070 == 1) ------------------------------------

_ANCIENT: dict[str, SpellInfo] = {
    "Edgeville Home Teleport": SpellInfo(_S.TELEPORT_HOME_ZAROS, "Cast"),
    "Paddewwa Teleport": SpellInfo(_S.ZAROSTELEPORT1),
    "Senntisten Teleport": SpellInfo(_S.ZAROSTELEPORT2),
    "Kharyrll Teleport": SpellInfo(_S.ZAROSTELEPORT3),
    "Lassar Teleport": SpellInfo(_S.ZAROSTELEPORT4),
    "Dareeyak Teleport": SpellInfo(_S.ZAROSTELEPORT5),
    "Carrallanger Teleport": SpellInfo(_S.ZAROSTELEPORT6),
    "Annakarl Teleport": SpellInfo(_S.ZAROSTELEPORT7),
    "Ghorrock Teleport": SpellInfo(_S.ZAROSTELEPORT8),
}

# -- Lunar spellbook (varbit 4070 == 2) --------------------------------------

_LUNAR: dict[str, SpellInfo] = {
    "Lunar Home Teleport": SpellInfo(_S.TELEPORT_HOME_LUNAR, "Cast"),
    "Moonclan Teleport": SpellInfo(_S.TELE_MOONCLAN),
    "Ourania Teleport": SpellInfo(_S.OURANIA_TELEPORT),
    "Waterbirth Teleport": SpellInfo(_S.TELE_WATERBIRTH),
    "Barbarian Teleport": SpellInfo(_S.TELE_BARB_OUT),
    "Khazard Teleport": SpellInfo(_S.TELE_KHAZARD),
    "Fishing Guild Teleport": SpellInfo(_S.TELE_FISH),
    "Catherby Teleport": SpellInfo(_S.TELE_CATHER),
    "Ice Plateau Teleport": SpellInfo(_S.TELE_GHORROCK),
}

# -- Arceuus spellbook (varbit 4070 == 3) ------------------------------------

_ARCEUUS: dict[str, SpellInfo] = {
    "Arceuus Home Teleport": SpellInfo(_S.TELEPORT_HOME_ARCEUUS, "Cast"),
    "Arceuus Library Teleport": SpellInfo(_S.TELEPORT_ARCEUUS_LIBRARY),
    "Draynor Manor Teleport": SpellInfo(_S.TELEPORT_DRAYNOR_MANOR),
    "Battlefront Teleport": SpellInfo(_S.TELEPORT_BATTLEFRONT),
    "Mind Altar Teleport": SpellInfo(_S.TELEPORT_MIND_ALTAR),
    "Respawn Teleport": SpellInfo(_S.TELEPORT_RESPAWN),
    "Salve Graveyard Teleport": SpellInfo(_S.TELEPORT_SALVE_GRAVEYARD),
    "Fenkenstrain's Castle Teleport": SpellInfo(_S.TELEPORT_FENKENSTRAIN_CASTLE),
    "West Ardougne Teleport": SpellInfo(_S.TELEPORT_WEST_ARDOUGNE),
    "Harmony Island Teleport": SpellInfo(_S.TELEPORT_HARMONY_ISLAND),
    "Cemetery Teleport": SpellInfo(_S.TELEPORT_CEMETERY),
    "Barrows Teleport": SpellInfo(_S.TELEPORT_BARROWS),
}

# -- Spells that share a name across spellbooks ------------------------------
# Keyed by (display_info, spellbook_varbit_value).

_AMBIGUOUS: dict[tuple[str, int], SpellInfo] = {
    ("Ape Atoll Teleport", 0): SpellInfo(_S.APE_TELEPORT),
    ("Ape Atoll Teleport", 3): SpellInfo(_S.TELEPORT_APE_ATOLL_DUNGEON),
}

# -- Combined lookup (unambiguous names only) --------------------------------

_BY_NAME: dict[str, SpellInfo] = {**_STANDARD, **_ANCIENT, **_LUNAR, **_ARCEUUS}


def lookup_spell(display_info: str, spellbook: int | None = None) -> SpellInfo | None:
    """Look up spell info by transport display_info string.

    For ambiguous names (same name on multiple spellbooks), pass the spellbook
    varbit value (from varbit 4070 in the transport's varbit requirements).
    """
    if spellbook is not None:
        result = _AMBIGUOUS.get((display_info, spellbook))
        if result is not None:
            return result
    return _BY_NAME.get(display_info)
