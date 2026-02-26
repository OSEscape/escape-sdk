from escape._models import Item, ItemIdentifier
from escape.constants import InterfaceID
from escape.constants._widgetfields import WidgetFields
from escape.geometry import Box
from escape.widget import Widget

_BUY_ACTIONS = {1: "Buy 1", 5: "Buy 5", 10: "Buy 10", 50: "Buy 50"}
_SELL_ACTIONS = {1: "Sell 1", 5: "Sell 5", 10: "Sell 10", 50: "Sell 50"}


class Shop:
    def __init__(self):
        from escape._services import Services

        s = Services.get()
        self._cache = s.cache
        self._keyboard = s.keyboard

    def is_open(self) -> bool:
        return InterfaceID.SHOPMAIN in self._cache.active_interfaces

    def get_items(self) -> list[Item]:
        if not self.is_open():
            return []
        w = Widget(InterfaceID.Shopmain.ITEMS)
        w.enable(WidgetFields.get_item_id)
        w.enable(WidgetFields.get_item_quantity)
        w.enable(WidgetFields.get_name)
        children = w.get_children()
        items: list[Item] = []
        for child in children:
            item_id = child.get("item_id", -1)
            if item_id > 0:
                items.append(
                    Item(
                        id=item_id,
                        name=child.get("name", ""),
                        quantity=child.get("item_quantity", 0),
                        noted=False,
                    )
                )
        return items

    def get_stock(self, identifier: ItemIdentifier) -> int:
        return sum(item.quantity for item in self.get_items() if item.matches(identifier))

    def contains(self, identifier: ItemIdentifier) -> bool:
        return self.get_stock(identifier) > 0

    def buy(self, identifier: ItemIdentifier, quantity: int = 1) -> bool:
        action = _BUY_ACTIONS.get(quantity)
        if action is None:
            return False
        return self._interact_shop_item(InterfaceID.Shopmain.ITEMS, identifier, action)

    def sell(self, identifier: ItemIdentifier, quantity: int = 1) -> bool:
        action = _SELL_ACTIONS.get(quantity)
        if action is None:
            return False
        return self._interact_shop_item(InterfaceID.Shopmain.ITEMS, identifier, action)

    def _interact_shop_item(self, widget_id: int, identifier: ItemIdentifier, action: str) -> bool:
        if not self.is_open():
            return False
        w = Widget(widget_id)
        w.enable(WidgetFields.get_item_id)
        w.enable(WidgetFields.get_name)
        w.enable(WidgetFields.get_bounds)
        children = w.get_children()
        for child in children:
            item_id = child.get("item_id", -1)
            if item_id <= 0:
                continue
            name = child.get("name", "")
            matched = (
                (item_id == identifier) if isinstance(identifier, int) else (identifier in name)
            )
            if not matched:
                continue
            bounds = child.get("bounds", {})
            if bounds.get("width", 0) <= 0:
                continue
            box = Box(bounds["x"], bounds["y"], bounds["width"], bounds["height"])
            return box.interact(option=action)
        return False

    def close(self) -> bool:
        if not self.is_open():
            return True
        self._keyboard.press_escape()
        return True
