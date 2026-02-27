"""Equipment tab module."""

from __future__ import annotations

from enum import Enum
from typing import ClassVar

from escape._cache.caches.item_cache import ItemContainerCache
from escape._models import Item, ItemContainer, ItemIdentifier
from escape.constants import InterfaceID  # pyright: ignore[reportMissingImports]
from escape.gametab import GameTab, GameTabs
from escape.widget import Buttons


class EquipmentSlots(Enum):
    HEAD = 0
    CAPE = 1
    NECK = 2
    WEAPON = 3
    TORSO = 4
    SHIELD = 5
    LEGS = 7
    HANDS = 9
    FEET = 10
    RING = 12
    AMMO = 13
    EXTRA_AMMO = 14


class Equipment(GameTabs, ItemContainer):
    TAB_TYPE = GameTab.EQUIPMENT
    CONTAINER_ID = ItemContainerCache.EQUIPMENT_ID
    _instance: Equipment | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def __init__(self):
        pass

    def _init(self):
        super().__init__(container_id=self.CONTAINER_ID, slot_count=14)
        self.bottom_buttons = Buttons(
            InterfaceID.WORNITEMS,
            [
                InterfaceID.Wornitems.EQUIPMENT,
                InterfaceID.Wornitems.PRICECHECKER,
                InterfaceID.Wornitems.DEATHKEEP,
                InterfaceID.Wornitems.CALL_FOLLOWER,
            ],
            [
                "View equipment stats",
                "View guide prices",
                "View items kept on death",
                "Call follower",
            ],
        )

        self.slots = Buttons(
            InterfaceID.WORNITEMS,
            [
                InterfaceID.Wornitems.SLOT0,
                InterfaceID.Wornitems.SLOT1,
                InterfaceID.Wornitems.SLOT2,
                InterfaceID.Wornitems.SLOT3,
                InterfaceID.Wornitems.SLOT4,
                InterfaceID.Wornitems.SLOT5,
                InterfaceID.Wornitems.SLOT7,
                InterfaceID.Wornitems.SLOT9,
                InterfaceID.Wornitems.SLOT10,
                InterfaceID.Wornitems.SLOT12,
                InterfaceID.Wornitems.SLOT13,
                InterfaceID.Wornitems.EXTRA_QUIVER_AMMO,
            ],
            list(EquipmentSlots.__members__.keys()),
            menu_text="Remove",
        )

    @property
    def items(self) -> list[Item | None]:
        cached = self._cache.get_item_container(self.CONTAINER_ID)
        if cached is None:
            self._items = []
            return self._items
        self._items = cached.items
        return self._items

    def open_equipment_view(self) -> bool:
        if not self.open():
            return False

        return self.bottom_buttons.interact("View equipment stats")

    def open_price_checker(self) -> bool:
        if not self.open():
            return False

        return self.bottom_buttons.interact("View guide prices")

    def open_view_kept_on_death(self) -> bool:
        if not self.open():
            return False

        return self.bottom_buttons.interact("View items kept on death")

    def call_follower(self) -> bool:
        if not self.open():
            return False

        return self.bottom_buttons.interact("Call follower")

    _SLOT_TO_ENUM: ClassVar[dict[int, EquipmentSlots]] = {
        slot.value: slot for slot in EquipmentSlots
    }

    def interact_slot(self, slot: EquipmentSlots, option: str | None = None) -> bool:
        if not self.open():
            return False

        if option:
            return self.slots.interact(slot.name, menu_option=option)
        return self.slots.interact(slot.name)

    def interact_item(self, identifier: ItemIdentifier, option: str | None = None) -> bool:
        if not self.open():
            return False

        slot_index = self.find_slot(identifier)
        if slot_index is None:
            return False

        slot_enum = self._SLOT_TO_ENUM.get(slot_index)
        if slot_enum is None:
            return False

        return self.interact_slot(slot_enum, option=option)
