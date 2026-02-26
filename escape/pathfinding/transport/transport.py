"""Transport classes for representing travel methods between locations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from escape.pathfinding.core.enums import TransportType

if TYPE_CHECKING:
    from escape.pathfinding.core.player_context import PlayerContext
from escape.pathfinding.core.world_point import (
    UNDEFINED,
    pack_world_point,
    unpack_world_plane,
    unpack_world_x,
    unpack_world_y,
)

# =============================================================================
# Constants
# =============================================================================

UNDEFINED_ORIGIN: int = UNDEFINED
UNDEFINED_DESTINATION: int = UNDEFINED
LOCATION_PERMUTATION: int = pack_world_point(-1 & 0x7FFF, -1 & 0x7FFF, 1)
"""Placeholder for transports that need permutation expansion (e.g., fairy rings)."""

# =============================================================================
# Variable Check Types
# =============================================================================


class VarCheckType(Enum):
    """Types of variable checks for transport requirements."""

    BIT_SET = "&"  # Check if bit is set: (value & required) > 0
    COOLDOWN_MINUTES = "@"  # Check cooldown: (now - value) > required minutes
    EQUAL = "="  # Check equality: value == required
    GREATER = ">"  # Check greater: value > required
    SMALLER = "<"  # Check smaller: value < required

    @classmethod
    def from_code(cls, code: str) -> VarCheckType | None:
        """Get VarCheckType from its code string."""
        for check in cls:
            if check.value == code:
                return check
        return None


@dataclass(frozen=True)
class VarbitRequirement:
    """A varbit requirement for a transport."""

    varbit_id: int
    value: int
    check_type: VarCheckType

    def check(self, context: PlayerContext) -> bool:
        """Check if this requirement is satisfied."""
        current = context.get_varbit(self.varbit_id)
        return self._compare(current, self.value, self.check_type)

    @staticmethod
    def _compare(current: int, required: int, check_type: VarCheckType) -> bool:
        """Compare current value against required using check type."""
        if check_type == VarCheckType.EQUAL:
            return current == required
        elif check_type == VarCheckType.GREATER:
            return current > required
        elif check_type == VarCheckType.SMALLER:
            return current < required
        elif check_type == VarCheckType.BIT_SET:
            return (current & required) > 0
        elif check_type == VarCheckType.COOLDOWN_MINUTES:
            now_minutes = int(time.time() / 60)
            return (now_minutes - current) > required
        return False


@dataclass(frozen=True)
class VarPlayerRequirement:
    """A varplayer requirement for a transport."""

    varplayer_id: int
    value: int
    check_type: VarCheckType

    def check(self, context: PlayerContext) -> bool:
        """Check if this requirement is satisfied."""
        current = context.get_varplayer(self.varplayer_id)
        return VarbitRequirement._compare(current, self.value, self.check_type)


# =============================================================================
# Item Requirements
# =============================================================================


@dataclass
class TransportItems:
    """Item requirements for using a transport."""

    items: list[list[int] | None] = field(default_factory=list)
    staves: list[list[int] | None] = field(default_factory=list)
    offhands: list[list[int] | None] = field(default_factory=list)
    quantities: list[int] = field(default_factory=list)

    def __bool__(self) -> bool:
        """TransportItems is truthy if it has any requirements."""
        return len(self.items) > 0


# =============================================================================
# Hardcoded Type-Level Requirements
# =============================================================================


def _check_type_requirements(
    transport_type: TransportType, context: PlayerContext, check_bank: bool = False
) -> bool:
    """Check hardcoded requirements that apply to all transports of a given type."""
    from escape.constants import ItemID, VarbitID

    if transport_type == TransportType.FAIRY_RING:
        if context.get_varbit(VarbitID.FAIRY2_QUEENCURE_QUEST) <= 39:
            return False
        elite_done = context.get_varbit(VarbitID.LUMBRIDGE_DIARY_ELITE_COMPLETE) == 1
        if not elite_done:
            has_staff = context.has_item(
                ItemID.DRAMEN_STAFF, check_bank=check_bank
            ) or context.has_item(ItemID.LUNAR_MOONCLAN_LIMINAL_STAFF, check_bank=check_bank)
            if not has_staff:
                return False
    elif transport_type == TransportType.GNOME_GLIDER:
        if not context.has_completed_quest("THE_GRAND_TREE"):
            return False
    elif transport_type == TransportType.MAGIC_MUSHTREE:
        if not context.has_completed_quest("BONE_VOYAGE"):
            return False
    elif transport_type == TransportType.SPIRIT_TREE:
        if not context.has_completed_quest("TREE_GNOME_VILLAGE"):
            return False
    elif transport_type == TransportType.MINECART:
        # Lovakengj minecarts cost 20 coins before The Forsaken Tower (varbit 7796=11)
        forsaken_tower_done = context.get_varbit(7796) == 11
        if not forsaken_tower_done:
            if not context.has_item(995, quantity=20, check_bank=check_bank):  # 995 = Coins
                return False

    return True


# =============================================================================
# Transport Class
# =============================================================================


@dataclass
class Transport:
    """A transport method between two world locations."""

    origin: int = UNDEFINED_ORIGIN
    destination: int = UNDEFINED_DESTINATION
    transport_type: TransportType = TransportType.TRANSPORT

    # Requirements
    skill_levels: dict[str, int] = field(default_factory=dict)
    quests: set[str] = field(default_factory=set)
    varbits: set[VarbitRequirement] = field(default_factory=set)
    varplayers: set[VarPlayerRequirement] = field(default_factory=set)
    item_requirements: TransportItems | None = None

    # Metadata
    duration: int = 0
    display_info: str | None = None
    is_consumable: bool = False
    max_wilderness_level: int = -1
    object_info: str | None = None

    @property
    def is_teleport(self) -> bool:
        """Check if this transport is a teleport (player-centered origin)."""
        return self.transport_type.is_teleport

    @property
    def is_quest_locked(self) -> bool:
        """Check if this transport requires quest completion."""
        return len(self.quests) > 0

    @property
    def has_undefined_origin(self) -> bool:
        """Check if origin is undefined (teleports)."""
        return self.origin == UNDEFINED_ORIGIN

    @property
    def has_undefined_destination(self) -> bool:
        """Check if destination is undefined."""
        return self.destination == UNDEFINED_DESTINATION

    def get_required_skill_level(self, skill: str) -> int:
        """Get required level for a skill (0 if not required)."""
        return self.skill_levels.get(skill.upper(), 0)

    def get_origin_coords(self) -> tuple[int, int, int] | None:
        """Get origin as (x, y, plane) tuple, or None if undefined."""
        if self.origin == UNDEFINED_ORIGIN:
            return None
        return (
            unpack_world_x(self.origin),
            unpack_world_y(self.origin),
            unpack_world_plane(self.origin),
        )

    def get_destination_coords(self) -> tuple[int, int, int] | None:
        """Get destination as (x, y, plane) tuple, or None if undefined."""
        if self.destination == UNDEFINED_DESTINATION:
            return None
        return (
            unpack_world_x(self.destination),
            unpack_world_y(self.destination),
            unpack_world_plane(self.destination),
        )

    def meets_requirements(
        self,
        context: PlayerContext,
        assume_items: bool = False,
        check_bank: bool = False,
        _skip_type_check: bool = False,
    ) -> bool:
        """Check if a player context meets all requirements for this transport."""
        # Check hardcoded type-level requirements (skipped when caller handles it)
        if not _skip_type_check and not _check_type_requirements(
            self.transport_type, context, check_bank=check_bank
        ):
            return False

        # Check skill levels
        for skill, required_level in self.skill_levels.items():
            actual_level = context.skill_levels.get(skill.upper(), 0)
            if actual_level < required_level:
                return False

        # Check quest requirements
        for quest in self.quests:
            if not context.has_completed_quest(quest):
                return False

        # Check varbit requirements
        for varbit_req in self.varbits:
            if not varbit_req.check(context):
                return False

        # Check varplayer requirements
        for varplayer_req in self.varplayers:
            if not varplayer_req.check(context):
                return False

        # Check item requirements (skip if assume_items=True)
        if not self.item_requirements or assume_items:
            return True
        return self._check_item_requirements(context, check_bank=check_bank)

    def _check_item_requirements(self, context: PlayerContext, check_bank: bool = False) -> bool:
        """Check if player has required items.

        When check_bank is True, also includes bank items in available items.
        """
        if not self.item_requirements:
            return True

        available_items = context.get_available_items(check_bank=check_bank)

        # Check each item slot
        for i, item_ids in enumerate(self.item_requirements.items):
            if item_ids is None:
                continue

            required_qty = (
                self.item_requirements.quantities[i]
                if i < len(self.item_requirements.quantities)
                else 1
            )
            found = False

            # Check if any variation of the item is available
            for item_id in item_ids:
                actual_qty = available_items.get(item_id, 0)
                if actual_qty >= required_qty:
                    found = True
                    break

            # Check staff alternatives
            if not found and i < len(self.item_requirements.staves):
                staves = self.item_requirements.staves[i]
                if staves:
                    for staff_id in staves:
                        if available_items.get(staff_id, 0) >= 1:
                            found = True
                            break

            # Check offhand alternatives
            if not found and i < len(self.item_requirements.offhands):
                offhands = self.item_requirements.offhands[i]
                if offhands:
                    for offhand_id in offhands:
                        if available_items.get(offhand_id, 0) >= 1:
                            found = True
                            break

            if not found:
                return False

        return True

    def __repr__(self) -> str:
        """Return string representation showing origin and destination."""
        origin_str = (
            "UNDEFINED" if self.origin == UNDEFINED_ORIGIN else str(self.get_origin_coords())
        )
        dest_str = (
            "UNDEFINED"
            if self.destination == UNDEFINED_DESTINATION
            else str(self.get_destination_coords())
        )
        return f"Transport({origin_str} -> {dest_str}, type={self.transport_type.name})"

    def __hash__(self) -> int:
        """Hash based on origin and destination."""
        return hash((self.origin, self.destination, self.transport_type))

    def __eq__(self, other: object) -> bool:
        """Equality based on origin, destination, and type."""
        if not isinstance(other, Transport):
            return NotImplemented
        return (
            self.origin == other.origin
            and self.destination == other.destination
            and self.transport_type == other.transport_type
        )


# =============================================================================
# Factory Functions
# =============================================================================


def merge_transports(origin_transport: Transport, dest_transport: Transport) -> Transport:
    """Merge an origin-only transport with a destination-only transport."""
    # Merge skill requirements (take max)
    merged_skills: dict[str, int] = {}
    for skill, level in origin_transport.skill_levels.items():
        merged_skills[skill] = max(level, dest_transport.skill_levels.get(skill, 0))
    for skill, level in dest_transport.skill_levels.items():
        if skill not in merged_skills:
            merged_skills[skill] = level

    return Transport(
        origin=origin_transport.origin,
        destination=dest_transport.destination,
        transport_type=origin_transport.transport_type,
        skill_levels=merged_skills,
        quests=origin_transport.quests | dest_transport.quests,
        varbits=origin_transport.varbits | dest_transport.varbits,
        varplayers=origin_transport.varplayers | dest_transport.varplayers,
        item_requirements=dest_transport.item_requirements,
        duration=max(origin_transport.duration, dest_transport.duration),
        display_info=dest_transport.display_info,
        is_consumable=origin_transport.is_consumable or dest_transport.is_consumable,
        max_wilderness_level=max(
            origin_transport.max_wilderness_level, dest_transport.max_wilderness_level
        ),
        object_info=origin_transport.object_info,
    )
