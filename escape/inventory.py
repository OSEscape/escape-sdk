"""Inventory tab module."""

from __future__ import annotations

import time

import escape.timing as timing
from escape._cache.caches.item_cache import ItemContainerCache
from escape._models import Item, ItemContainer, ItemIdentifier
from escape._resources import varps
from escape.constants import InterfaceID, VarbitID
from escape.gametab import GameTab, GameTabs
from escape.geometry import Box
from escape.widget import Widget, WidgetFields


class Inventory(GameTabs, ItemContainer):
    TAB_TYPE = GameTab.INVENTORY
    INVENTORY_ID = ItemContainerCache.INVENTORY_ID
    _instance: Inventory | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def __init__(self):
        pass

    def _init(self):
        super().__init__(container_id=self.INVENTORY_ID, slot_count=28)
        from escape._services import Services

        s = Services.get()
        self._menu = s.menu
        self._keyboard = s.keyboard
        self._mouse = s.mouse
        self._slots: list[Box] | None = None

    def _fetch_slot_bounds(self) -> list[Box]:
        if InterfaceID.BANKSIDE in self._cache.active_interfaces:
            widget = Widget(InterfaceID.Bankside.ITEMS).enable(WidgetFields.get_bounds)
        else:
            widget = Widget(InterfaceID.Inventory.ITEMS).enable(WidgetFields.get_bounds)

        children = widget.get_children()
        boxes = []
        for child in children:
            b = child.get("bounds", {"x": 0, "y": 0, "width": 0, "height": 0})
            if b.get("width", 0) > 0 and b.get("height", 0) > 0:
                boxes.append(Box(b["x"], b["y"], b["width"], b["height"]))
        return boxes

    @property
    def slots(self) -> list[Box]:
        if self._slots is None:
            self._slots = self._fetch_slot_bounds()
        return self._slots

    def refresh_slots(self):
        self._slots = None

    @property
    def items(self) -> list[Item | None]:
        cached = self._cache.get_item_container(self.INVENTORY_ID)
        if cached is None:
            self._items = []
            return self._items
        self._items = cached.items
        return self._items

    def get_slot_box(self, slot_index: int) -> Box:
        return self.slots[slot_index]

    def hover_slot(self, slot_index: int) -> bool:
        slots = self.slots
        if 0 <= slot_index < len(slots):
            slots[slot_index].hover()
            return True
        return False

    def hover(self, identifier: ItemIdentifier) -> bool:
        found_slots = self.find_slots(identifier)
        if not found_slots:
            return False

        if self.hover_slot(found_slots[0]):
            return self._menu.wait_has_option("Examine")
        return False

    def interact_slot(
        self, slot_index: int, option: str | None = None, action: str | None = None
    ) -> bool:
        slots = self.slots
        if not (0 <= slot_index < len(slots)):
            return False
        print(
            f"Interacting with slot {slot_index} (option={option}, action={action}) with bounds {slots[slot_index]}"
        )
        return slots[slot_index].interact(option=option, action=action)

    def interact_item(
        self,
        identifier: ItemIdentifier,
        option: str | None = None,
        action: str | None = None,
    ) -> bool:
        slot = self.find_slot(identifier)
        if slot is None:
            return False

        return self.interact_slot(slot, option=option, action=action)

    def is_shift_drop_enabled(self) -> bool:
        varbit_value = varps.get_varbit(VarbitID.DESKTOP_SHIFTCLICKDROP_ENABLED)
        return varbit_value == 1 if varbit_value is not None else False

    def wait_drop_option(self, timeout: float = 0.5) -> bool:
        return timing.wait_until(
            lambda: self._menu.has_option("Drop"), timeout=timeout, poll_interval=0.01
        )

    def drop(self, *identifiers: ItemIdentifier, force_shift: bool = False) -> int:
        all_slots = []
        for identifier in identifiers:
            all_slots.extend(self.find_slots(identifier))

        if not all_slots:
            return 0

        return self.drop_slots(all_slots, force_shift=force_shift)

    def drop_slots(self, slot_indices: list[int], force_shift: bool = False) -> int:
        if not slot_indices:
            return 0

        use_shift_drop = force_shift or self.is_shift_drop_enabled()
        dropped_count = 0

        if use_shift_drop:
            self._keyboard.hold("shift")
            time.sleep(0.025)

        try:
            for slot_index in slot_indices:
                self.hover_slot(slot_index)

                if not self.wait_drop_option():
                    continue

                if self._menu.click_option("Drop"):
                    dropped_count += 1
        finally:
            if use_shift_drop:
                self._keyboard.release("shift")

        return dropped_count

    def select_slot(self, slot_index: int) -> bool:
        if not (0 <= slot_index < 28):
            return False

        if not self.hover_slot(slot_index):
            return False
        if not self._menu.wait_has_menu_action("WIDGET_TARGET"):
            return False
        if self._menu.click_option_action("WIDGET_TARGET"):
            return timing.wait_until(self.is_selected, 1, 0.01)
        return False

    def is_selected(self) -> bool:
        widget = self._cache.selected_widget
        widget_id = widget.selected_widget_id if widget else -1
        return widget_id == InterfaceID.Inventory.ITEMS

    def get_selected_item_slot(self) -> int:
        widget = self._cache.selected_widget
        return widget.index if widget else -1

    def unselect(self) -> bool:
        if not self.is_selected():
            return True

        return self._menu.click_option_action("CANCEL")

    def select(self, identifier: ItemIdentifier) -> bool:
        if not self.open():
            return False

        target_slot = self.find_slot(identifier)

        if target_slot is not None:
            return self.select_slot(target_slot)
        return False

    def use_slot_on_slot(
        self,
        slot_1: int,
        slot_2: int,
    ) -> bool:
        if self.select_slot(slot_1):
            return self.interact_slot(slot_2, action="WIDGET_TARGET_ON_WIDGET")

        return False

    def use_on(self, item_1: ItemIdentifier, item_2: ItemIdentifier) -> bool:
        slot_1 = self.find_slot(item_1)
        slot_2 = self.find_slot(item_2)

        if slot_1 is not None and slot_2 is not None:
            return self.use_slot_on_slot(slot_1, slot_2)

        return False
