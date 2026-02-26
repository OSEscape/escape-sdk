import json
import math
import random
from pathlib import Path

import escape.timing as timing
from escape._cache.caches.item_cache import ItemContainerCache
from escape._logger import logger
from escape._models import Item, ItemContainer, ItemIdentifier
from escape._resources import varps
from escape.constants import (  # pyright: ignore[reportMissingImports]
    InterfaceID,
    VarbitID,
    VarClientID,
)
from escape.geometry import Box
from escape.widget import Widget, WidgetFields

_BUTTON_WIDGETS = [
    ("deposit_all_button", InterfaceID.Bankmain.DEPOSITINV),
    ("deposit_gear_button", InterfaceID.Bankmain.DEPOSITWORN),
    ("withdraw_item_button", InterfaceID.Bankmain.SWAP_INSERT),
    ("withdraw_note_button", InterfaceID.Bankmain.NOTE),
    ("withdraw_1_button", InterfaceID.Bankmain.QUANTITY1),
    ("withdraw_5_button", InterfaceID.Bankmain.QUANTITY5),
    ("withdraw_10_button", InterfaceID.Bankmain.QUANTITY10),
    ("withdraw_x_button", InterfaceID.Bankmain.QUANTITYX),
    ("withdraw_all_button", InterfaceID.Bankmain.QUANTITYALL),
    ("search_button", InterfaceID.Bankmain.SEARCH),
    ("settings_button", InterfaceID.Bankmain.MENU_BUTTON),
    ("bank_area", InterfaceID.Bankmain.ITEMS),
]

_BANKPIN_BUTTON_IDS = [
    InterfaceID.BankpinKeypad.A,
    InterfaceID.BankpinKeypad.B,
    InterfaceID.BankpinKeypad.C,
    InterfaceID.BankpinKeypad.D,
    InterfaceID.BankpinKeypad.E,
    InterfaceID.BankpinKeypad.F,
    InterfaceID.BankpinKeypad.G,
    InterfaceID.BankpinKeypad.H,
    InterfaceID.BankpinKeypad.I,
    InterfaceID.BankpinKeypad.J,
]

_CREDENTIALS_PATH = Path.home() / "alpine" / "credentials" / "credentials.json"


class Bank(ItemContainer):
    CONTAINER_ID = ItemContainerCache.BANK_ID
    ITEM_SLOT_HEIGHT = 36
    _instance: Bank | None = None

    deposit_all_button: Box
    deposit_gear_button: Box
    withdraw_item_button: Box
    withdraw_note_button: Box
    withdraw_1_button: Box
    withdraw_5_button: Box
    withdraw_10_button: Box
    withdraw_x_button: Box
    withdraw_all_button: Box
    search_button: Box
    settings_button: Box
    bank_area: Box
    tab_buttons: list[Box]
    quantity_buttons: dict[str, Box]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def __init__(self):
        pass

    def _init(self):
        super().__init__(container_id=self.CONTAINER_ID, slot_count=920)
        from escape._services import Services
        from escape.equipment import Equipment
        from escape.inventory import Inventory

        s = Services.get()
        self._cache = s.cache
        self._mouse = s.mouse
        self._keyboard = s.keyboard
        self._inventory = Inventory()
        self._equipment = Equipment()
        self.is_setup = False
        self._withdraw_counts: dict[str, int] = {}

        self.capacity_widget = Widget(InterfaceID.Bankmain.CAPACITY)
        self.capacity_widget.enable(WidgetFields.get_text)

        self.item_widget = Widget(InterfaceID.Bankmain.ITEMS)
        self.item_widget.enable(WidgetFields.get_bounds)
        self.item_widget.enable(WidgetFields.is_hidden)

    def _setup_bounds(self):
        widgets = [Widget(wid).enable(WidgetFields.get_bounds) for _, wid in _BUTTON_WIDGETS]
        results = Widget.get_batch(widgets)
        for (attr, _), result in zip(_BUTTON_WIDGETS, results, strict=True):
            b = result.get("bounds", {"x": 0, "y": 0, "width": 0, "height": 0})
            if b.get("width", 0) > 0 and b.get("height", 0) > 0:
                setattr(self, attr, Box(b["x"], b["y"], b["width"], b["height"]))
        self.quantity_buttons = {
            "1": self.withdraw_1_button,
            "5": self.withdraw_5_button,
            "10": self.withdraw_10_button,
            "X": self.withdraw_x_button,
            "All": self.withdraw_all_button,
        }
        tab_widget = Widget(InterfaceID.Bankmain.TABS).enable(WidgetFields.get_bounds)
        children = tab_widget.get_children()
        self.tab_buttons = []
        for child in children:
            b = child.get("bounds", {"x": 0, "y": 0, "width": 0, "height": 0})
            if b.get("width", 0) > 0 and b.get("height", 0) > 0:
                self.tab_buttons.append(Box(b["x"], b["y"], b["width"], b["height"]))

    def refresh_bounds(self):
        self.is_setup = False

    @property
    def items(self) -> list[Item | None]:
        cached = self._cache.get_item_container(self.CONTAINER_ID)
        if cached is None:
            self._items = []
            return self._items
        self._items = cached.items
        return self._items

    def is_open(self, solve_bankpin: bool = True) -> bool:
        if self.is_pin_open() and solve_bankpin:
            self.enter_bank_pin()
        return InterfaceID.BANKMAIN in self._cache.active_interfaces

    def _ensure_setup(self) -> bool:
        if not self.is_open():
            return False
        if not self.is_setup:
            text = self.capacity_widget.get().get("text", None)
            if text:
                self.slot_count = int(text)
            self._setup_bounds()
            self.is_setup = True
        return True

    def get_open_tab(self) -> int | None:
        if not self.is_open():
            return None
        return varps.get_varbit(VarbitID.BANK_CURRENTTAB)

    def get_itemcount_in_tab(self, tab_index: int) -> int:
        if tab_index > 8 or tab_index < 0:
            raise ValueError("tab_index must be between 0 and 8")

        if tab_index == 0:
            tabcounts = 0
            for i in range(1, 9):
                varbit_id = getattr(VarbitID, f"BANK_TAB_{i}")
                count = varps.get_varbit(varbit_id)
                if count is None:
                    count = 0
                tabcounts += count
            return self.get_total_count() - tabcounts

        varbit_id = getattr(VarbitID, f"BANK_TAB_{tab_index}")
        count = varps.get_varbit(varbit_id)
        return count if count is not None else 0

    def get_current_x_amount(self) -> int | None:
        return varps.get_varbit(VarbitID.BANK_REQUESTEDQUANTITY)

    def set_noted_mode(self, noted: bool) -> bool:
        if not self._ensure_setup():
            return False

        current_value = varps.get_varbit(VarbitID.BANK_WITHDRAWNOTES)
        currently_noted = current_value is not None and current_value > 0

        logger.info(f"Setting noted mode to {noted}, currently {currently_noted}")

        if not currently_noted and noted:
            self.withdraw_note_button.interact(option="Enable Notes")

        if currently_noted and not noted:
            self.withdraw_item_button.interact(option="Disable notes")

        def check_noted():
            value = varps.get_varbit(VarbitID.BANK_WITHDRAWNOTES)
            return value == (1 if noted else 0) if value is not None else False

        return timing.wait_until(check_noted, timeout=2.0)

    def is_search_open(self) -> bool:
        if not self.is_open():
            return False
        return self._cache.get_varc(VarClientID.MESLAYERMODE) == 11

    def is_x_query_open(self) -> bool:
        if not self.is_open():
            return False
        return self._cache.get_varc(VarClientID.MESLAYERMODE) == 7

    def get_search_text(self) -> str:
        if not self.is_search_open():
            return ""
        result = self._cache.get_varc(VarClientID.MESLAYERINPUT)
        return str(result) if result is not None else ""

    def open_search(self) -> bool:
        if not self._ensure_setup():
            return False
        if self.is_search_open():
            return True
        self.search_button.interact(option="Search")
        return self.is_search_open()

    def search_item(self, text: str) -> bool:
        if not self.open_search():
            return False
        self._keyboard.type(text)
        return timing.wait_until(lambda: self.get_search_text() == text, timeout=0.5)

    def itemcounts_per_tab(self):
        counts = []
        counts.append(self.get_itemcount_in_tab(0))
        for i in range(1, 9):
            counts.append(self.get_itemcount_in_tab(i))
        return counts

    def get_index(self, identifier: ItemIdentifier) -> int | None:
        if not self.contains(identifier):
            return None
        return self.find_slot(identifier)

    def get_item_box(self, identifier: ItemIdentifier) -> Box | None:
        index = self.get_index(identifier)
        if index is None:
            return None
        result = self.item_widget.get_child(index)
        try:
            if result["is_hidden"]:
                return None
            bounds = result["bounds"]
            return Box(bounds["x"], bounds["y"], bounds["width"], bounds["height"])
        except Exception as e:
            logger.error(f"Error getting item area: {e}")
            return None

    def is_box_clickable(self, box: Box) -> bool:
        return (
            self.bank_area.y
            <= box.y
            <= self.bank_area.y + self.bank_area.height - self.ITEM_SLOT_HEIGHT
        )

    def get_scroll_count(self, box: Box) -> tuple[int, bool]:
        step = 45
        min_y = self.bank_area.y
        max_y = self.bank_area.y + self.bank_area.height - self.ITEM_SLOT_HEIGHT
        y = box.y

        if min_y <= y <= max_y:
            return 0, False

        if y < min_y:
            scroll_up = True
            k_min = math.ceil((min_y - y) / step)
            k_max = math.floor((max_y - y) / step)
            if k_max < k_min:
                k_max = k_min
            k = random.randint(k_min, k_max)
            return k, scroll_up

        else:
            scroll_up = False
            k_min = math.ceil((y - max_y) / step)
            k_max = math.floor((y - min_y) / step)
            if k_max < k_min:
                k_max = k_min
            k = random.randint(k_min, k_max)
            return k, scroll_up

    def make_item_visible(self, identifier: ItemIdentifier) -> Box | None:
        if not self._ensure_setup():
            return None
        if not self.contains(identifier):
            raise ValueError("Item not found in bank")

        box = self.get_item_box(identifier)

        if box is None:
            tab_index = self.get_tab_index(identifier)
            if tab_index is None:
                return None
            if not self.open_tab(tab_index):
                return None
            box = self.get_item_box(identifier)
            if box is None:
                return None

        scroll_count, scroll_up = self.get_scroll_count(box)

        if scroll_count != 0:
            self.bank_area.hover()
            self._mouse.scroll(up=scroll_up, count=scroll_count)
            timing.sleep(0.05)

            box = self.get_item_box(identifier)
            if box is None:
                return None

        logger.info(f"found box: {box}")

        if box is not None and self.is_box_clickable(box):
            return box
        else:
            return None

    def get_tab_index(self, identifier: ItemIdentifier) -> int | None:
        index = self.get_index(identifier)
        if index is None:
            return None
        tabcounts = self.itemcounts_per_tab()
        cumcount = 0
        for i in range(1, len(tabcounts)):
            cumcount += tabcounts[i]
            if index < cumcount:
                return i
        return None

    def open_tab(self, tab_index: int) -> bool:
        if not self._ensure_setup():
            return False
        if tab_index < 0 or tab_index > 8:
            raise ValueError("tab_index must be between 0 and 8")
        if self.get_open_tab() == tab_index:
            return True
        self.tab_buttons[tab_index].interact(option=f"View tab {tab_index}")
        return timing.wait_until(lambda: self.get_open_tab() == tab_index, timeout=2.0)

    def _ensure_quantity(self, button: str) -> bool:
        allowed = ["1", "5", "10", "X", "All"]
        current = varps.get_varbit(VarbitID.BANK_QUANTITY_TYPE)
        if current == allowed.index(button):
            return True
        return self.set_withdraw_quantity(button)

    def _quantity_category(self, quantity: int) -> str:
        if quantity == 1:
            return "1"
        if quantity == 5:
            return "5"
        if quantity == 10:
            return "10"
        if quantity <= 0:
            return "All"
        return str(quantity)

    def _optimal_button(self) -> str | None:
        """Return the best bank button for the most common withdrawal quantity."""
        if not self._withdraw_counts:
            return None
        for category, _ in sorted(self._withdraw_counts.items(), key=lambda kv: kv[1], reverse=True):
            if category in ("1", "5", "10", "All"):
                return category
            # Custom X amount — only use X button if value already matches
            try:
                if self.get_current_x_amount() == int(category):
                    return "X"
            except ValueError:
                pass
        return None

    def _ensure_optimal_quantity(self) -> None:
        button = self._optimal_button()
        if button is not None:
            self._ensure_quantity(button)

    def set_withdraw_quantity(self, quantity: str, wait: bool = True) -> bool:
        if not self._ensure_setup():
            return False

        allowed = ["1", "5", "10", "X", "All"]
        if quantity not in allowed:
            raise ValueError("quantity must be one of '1', '5', '10', 'X', 'All'")
        x_amount = varps.get_varbit(VarbitID.BANK_REQUESTEDQUANTITY)
        if quantity == "X":
            allowed[3] = str(x_amount) if x_amount is not None else "X"
        index = allowed.index(quantity)
        self.quantity_buttons[quantity].interact(option="Default quantity: " + quantity)

        if not wait:
            return True

        def check_quantity():
            value = varps.get_varbit(VarbitID.BANK_QUANTITY_TYPE)
            return value == index if value is not None else False

        return timing.wait_until(check_quantity, timeout=1)

    def deposit_all(self, wait: bool = True) -> bool:
        if not self._ensure_setup():
            return False

        start = self._inventory.get_total_quantity()
        if start == 0:
            return True

        self.deposit_all_button.interact(option="Deposit inventory")

        if not wait:
            return True

        return timing.wait_until(lambda: self._inventory.get_total_quantity() < start, timeout=2.0)

    def deposit_equipment(self, wait: bool = True) -> bool:
        if not self._ensure_setup():
            return False

        start = self._equipment.get_total_count()
        self.deposit_gear_button.interact(option="Deposit worn")

        if not wait:
            return True

        return timing.wait_until(lambda: self._equipment.get_total_count() < start, timeout=2.0)
    
    def hover(self, identifier: ItemIdentifier, quantity: int | None = None, noted: bool | None = None) -> bool:
        if not self.is_open():
            return False

        if not self.contains(identifier):
            return False

        area = self.make_item_visible(identifier)
        if area is None:
            return False

        if noted is not None:
            self.set_noted_mode(noted)

        if quantity is not None:
            category = self._quantity_category(quantity)
            self._withdraw_counts[category] = self._withdraw_counts.get(category, 0) + 1
            self._ensure_optimal_quantity()
      
        return area.hover("Withdraw-1 ")

    def withdraw(self, identifier: ItemIdentifier, quantity: int = 1, noted: bool = False) -> bool:
        if not self.is_open():
            return False

        if not self.contains(identifier):
            return False

        area = self.make_item_visible(identifier)
        if area is None:
            return False

        self.set_noted_mode(noted)

        category = self._quantity_category(quantity)
        self._withdraw_counts[category] = self._withdraw_counts.get(category, 0) + 1
        self._ensure_optimal_quantity()
        print(self._withdraw_counts)

        start_count = self._inventory.get_total_quantity()

        if quantity == 1:
            area.interact(option="Withdraw-1")
        elif quantity == 5:
            area.interact(option="Withdraw-5")
        elif quantity == 10:
            area.interact(option="Withdraw-10")
        elif quantity <= 0:
            area.interact(option="Withdraw-All")
        elif self.get_current_x_amount() == quantity:
            self._ensure_quantity("X")
            area.interact(option=f"Withdraw-{quantity}")
        else:
            area.interact(option="Withdraw-X")
            timing.wait_until(lambda: self.is_x_query_open(), timeout=3.0)
            self._keyboard.type(str(quantity))
            self._keyboard.press_enter()

        return timing.wait_until(
            lambda: self._inventory.get_total_quantity() > start_count, timeout=2.0
        )

    def deposit(self, identifier: ItemIdentifier, quantity: int = 0) -> bool:
        if not self.is_open():
            return False

        slot = self._inventory.find_slot(identifier)
        if slot is None:
            return False

        start_count = self._inventory.get_total_quantity()

        category = self._quantity_category(quantity)
        self._withdraw_counts[category] = self._withdraw_counts.get(category, 0) + 1
        self._ensure_optimal_quantity()
        print(self._withdraw_counts)

        if quantity == 1:
            self._inventory.interact_slot(slot, option="Deposit-1")
        elif quantity == 5:
            self._inventory.interact_slot(slot, option="Deposit-5")
        elif quantity == 10:
            self._inventory.interact_slot(slot, option="Deposit-10")
        elif quantity <= 0:
            self._inventory.interact_slot(slot, option="Deposit-All")
        elif self.get_current_x_amount() == quantity:
            self._ensure_quantity("X")
            self._inventory.interact_slot(slot, option=f"Deposit-{quantity}")
        else:
            self._inventory.interact_slot(slot, option="Deposit-X")
            timing.wait_until(lambda: self.is_x_query_open(), timeout=3.0)
            self._keyboard.type(str(quantity))
            self._keyboard.press_enter()

        return timing.wait_until(
            lambda: self._inventory.get_total_quantity() < start_count, timeout=2.0
        )

    def deposit_all_except(self, identifiers: list[ItemIdentifier]) -> bool:
        if not self.is_open():
            return False

        inv = self._inventory
        keep_ids = {inv.items[s].id for ident in identifiers for s in inv.find_slots(ident) if inv.items[s] is not None}
        deposited: set[int] = set()
        for item in self._inventory.items:
            if item is None or item.id in keep_ids or item.id in deposited:
                continue
            deposited.add(item.id)
            print(f"Depositing item {item.id}")
            self.deposit(item.id)

        return True

    def close(self) -> bool:
        if not self.is_open():
            return True
        self._keyboard.press_escape()
        result = timing.wait_until(lambda: not self.is_open(), timeout=2.0)
        if not result:
            logger.warning("Failed to close bank with escape key")
        return result

    def is_pin_open(self) -> bool:
        return InterfaceID.BANKPIN_KEYPAD in self._cache.active_interfaces

    def _get_pin_digit_mapping(self) -> dict[str, Box]:
        """Read the current digit-to-button mapping from the shuffled bank PIN keypad."""
        widgets = [
            Widget(wid).enable(WidgetFields.get_text).enable(WidgetFields.get_bounds)
            for wid in _BANKPIN_BUTTON_IDS
        ]
        children = Widget.get_batch_children(widgets)

        mapping: dict[str, Box] = {}
        for i in range(0, len(children), 2):
            bounds_data = children[i].get("bounds", {})
            text_data = children[i + 1].get("text", "")

            if bounds_data.get("width", 0) > 0 and text_data:
                box = Box(bounds_data["x"], bounds_data["y"], bounds_data["width"], bounds_data["height"])
                mapping[text_data.strip()] = box

        return mapping

    def enter_bank_pin(self) -> bool:
        """Enter the bank PIN when the keypad is open.

        Reads the PIN from the credentials file and clicks the correct
        shuffled buttons for each digit. Returns True if the PIN interface
        closes after entry.
        """
        if not self.is_pin_open():
            return False

        creds = json.loads(_CREDENTIALS_PATH.read_text())
        pin = str(creds["bank_pin"])

        if len(pin) != 4:
            logger.error(f"Bank PIN must be 4 digits, got {len(pin)}")
            return False

        for digit in pin:
            if not self.is_pin_open():
                break

            mapping = self._get_pin_digit_mapping()
            box = mapping.get(digit)

            if box is None:
                logger.error("Could not find button for PIN digit")
                return False

            box.interact()
            timing.sleep(0.6, 1.0)

        return timing.wait_until(lambda: not self.is_pin_open(), timeout=5.0)

    @property
    def free_slots(self) -> int:
        return self.slot_count - self.get_total_count()
