"""Player context for pathfinding decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from escape._resources import varps

if TYPE_CHECKING:
    from escape._resources.questdata import Quest

# =============================================================================
# OSRS Skill Definitions
# =============================================================================

SKILLS: tuple[str, ...] = (
    "ATTACK",
    "DEFENCE",
    "STRENGTH",
    "HITPOINTS",
    "RANGED",
    "PRAYER",
    "MAGIC",
    "COOKING",
    "WOODCUTTING",
    "FLETCHING",
    "FISHING",
    "FIREMAKING",
    "CRAFTING",
    "SMITHING",
    "MINING",
    "HERBLORE",
    "AGILITY",
    "THIEVING",
    "SLAYER",
    "FARMING",
    "RUNECRAFT",
    "HUNTER",
    "CONSTRUCTION",
)

# Skill name -> index mapping for efficient lookups
SKILL_INDEX: dict[str, int] = {skill: i for i, skill in enumerate(SKILLS)}

# Maximum levels
MAX_SKILL_LEVEL: int = 99
MAX_TOTAL_LEVEL: int = 2376  # 99 * 24
MAX_COMBAT_LEVEL: int = 126
MAX_QUEST_POINTS: int = 350  # Approximate, increases with new quests

# =============================================================================
# Quest Name Mapping (transport name -> quest ID)
# =============================================================================

# Manual overrides for quest names that don't auto-normalize from questdata.
_QUEST_NAME_OVERRIDES: dict[str, int] = {
    "FREEING_KING_AWOWOGEI": 179,  # "Recipe for Disaster - King Awowogei"
}

# Lazy-built mapping: transport quest name -> Quest object
_quest_by_transport_name: dict[str, Quest] | None = None


def _get_quest_by_transport_name() -> dict[str, Quest]:
    """Build mapping from transport quest name to Quest object (lazy)."""
    global _quest_by_transport_name
    if _quest_by_transport_name is not None:
        return _quest_by_transport_name

    from escape._resources.questdata import ALL_QUESTS

    override_by_id = {qid: name for name, qid in _QUEST_NAME_OVERRIDES.items()}
    mapping: dict[str, Quest] = {}

    for quest in ALL_QUESTS:
        if quest.id in override_by_id:
            mapping[override_by_id[quest.id]] = quest
        else:
            mapping[quest.name.upper().replace(" ", "_")] = quest

    _quest_by_transport_name = mapping
    return mapping


# =============================================================================
# PlayerContext Dataclass
# =============================================================================


def _default_skill_levels() -> dict[str, int]:
    """Create default maxed skill levels."""
    return dict.fromkeys(SKILLS, MAX_SKILL_LEVEL)


@dataclass
class PlayerContext:
    """Player state for determining which transports are available.

    Defaults to a maxed player with all transports available.
    """

    # Position
    position: tuple[int, int, int] = (0, 0, 0)

    # Skill levels (default: maxed)
    skill_levels: dict[str, int] = field(default_factory=_default_skill_levels)
    total_level: int = MAX_TOTAL_LEVEL
    combat_level: int = MAX_COMBAT_LEVEL

    # Quest state
    quest_points: int = MAX_QUEST_POINTS

    # Items
    inventory: dict[int, int] = field(default_factory=dict)
    equipment: dict[int, int] = field(default_factory=dict)
    bank: dict[int, int] | None = None
    rune_pouch: dict[int, int] = field(default_factory=dict)

    # Membership
    member: bool = True

    # Cached lookups (built lazily per pathfinding call, not init params)
    _available_items_no_bank: dict[int, int] | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _available_items_with_bank: dict[int, int] | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _quest_cache: dict[str, bool] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _varbit_cache: dict[int, int] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _varplayer_cache: dict[int, int] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def get_available_items(self, check_bank: bool = False) -> dict[int, int]:
        """Get merged inventory+equipment+rune_pouch (and optionally bank) item dict, cached lazily."""
        if check_bank:
            if self._available_items_with_bank is None:
                items = dict(self.inventory)
                for item_id, qty in self.equipment.items():
                    items[item_id] = items.get(item_id, 0) + qty
                for item_id, qty in self.rune_pouch.items():
                    items[item_id] = items.get(item_id, 0) + qty
                if self.bank is not None:
                    for item_id, qty in self.bank.items():
                        items[item_id] = items.get(item_id, 0) + qty
                self._available_items_with_bank = items
            return self._available_items_with_bank
        else:
            if self._available_items_no_bank is None:
                items = dict(self.inventory)
                for item_id, qty in self.equipment.items():
                    items[item_id] = items.get(item_id, 0) + qty
                for item_id, qty in self.rune_pouch.items():
                    items[item_id] = items.get(item_id, 0) + qty
                self._available_items_no_bank = items
            return self._available_items_no_bank

    def get_skill_level(self, skill: str) -> int:
        """Get the level for a skill (1 if not found)."""
        return self.skill_levels.get(skill.upper(), 1)

    def has_completed_quest(self, quest_name: str) -> bool:
        """Check if a quest is completed via live varbit/varp lookup (cached per context)."""
        cached = self._quest_cache.get(quest_name)
        if cached is not None:
            return cached

        quest = _get_quest_by_transport_name().get(quest_name)
        if quest is None:
            self._quest_cache[quest_name] = True
            return True  # Unknown quest, don't block transport

        if quest.varbit is not None:
            state = varps.get_varbit(quest.varbit)
        elif quest.varp is not None:
            state = varps.get_varp_value(quest.varp)
        else:
            self._quest_cache[quest_name] = True
            return True  # No way to check, assume completed

        result = state is not None and state >= quest.end_state
        self._quest_cache[quest_name] = result
        return result

    def get_varbit(self, varbit_id: int, default: int = 0) -> int:
        """Get a varbit value via live cache lookup (cached per context)."""
        cached = self._varbit_cache.get(varbit_id)
        if cached is not None:
            return cached

        value = varps.get_varbit(varbit_id)
        result = value if value is not None else default
        self._varbit_cache[varbit_id] = result
        return result

    def get_varplayer(self, varplayer_id: int, default: int = 0) -> int:
        """Get a varplayer value via live cache lookup (cached per context)."""
        cached = self._varplayer_cache.get(varplayer_id)
        if cached is not None:
            return cached

        value = varps.get_varp_value(varplayer_id)
        result = value if value is not None else default
        self._varplayer_cache[varplayer_id] = result
        return result

    def has_item(self, item_id: int, quantity: int = 1, check_bank: bool = False) -> bool:
        """Check if player has an item in sufficient quantity."""
        total = (
            self.inventory.get(item_id, 0)
            + self.equipment.get(item_id, 0)
            + self.rune_pouch.get(item_id, 0)
        )
        if check_bank and self.bank is not None:
            total += self.bank.get(item_id, 0)
        return total >= quantity

    def has_any_item(self, item_ids: list[int], check_bank: bool = False) -> bool:
        """Check if player has any of the specified items."""
        return any(self.has_item(item_id, 1, check_bank) for item_id in item_ids)
