from __future__ import annotations

from escape.constants import InterfaceID
from escape.constants._widgetfields import WidgetFields
from escape.widget import Widget

_CONTINUABLE_GROUPS: set[int] = {
    InterfaceID.CHAT_LEFT,
    InterfaceID.CHAT_RIGHT,
    InterfaceID.MESSAGEBOX,
    InterfaceID.OBJECTBOX,
    InterfaceID.LEVELUP_DISPLAY,
    InterfaceID.GRAPHICBOX,
}

_ALL_DIALOG_GROUPS: set[int] = _CONTINUABLE_GROUPS | {InterfaceID.CHATMENU}

_TEXT_WIDGETS: dict[int, int] = {
    InterfaceID.CHAT_LEFT: InterfaceID.ChatLeft.TEXT,
    InterfaceID.CHAT_RIGHT: InterfaceID.ChatRight.TEXT,
    InterfaceID.MESSAGEBOX: InterfaceID.Messagebox.TEXT,
    InterfaceID.OBJECTBOX: InterfaceID.Objectbox.TEXT,
    InterfaceID.GRAPHICBOX: InterfaceID.Graphicbox.TEXT,
}

_NAME_WIDGETS: dict[int, int] = {
    InterfaceID.CHAT_LEFT: InterfaceID.ChatLeft.NAME,
    InterfaceID.CHAT_RIGHT: InterfaceID.ChatRight.NAME,
}


class Dialog:
    def __init__(self):
        from escape._services import Services

        s = Services.get()
        self._cache = s.cache
        self._keyboard = s.keyboard

    def _active_dialog_group(self) -> int | None:
        for group in self._cache.active_interfaces:
            if group in _ALL_DIALOG_GROUPS:
                return group
        return None

    def is_open(self) -> bool:
        return self._active_dialog_group() is not None

    def can_continue(self) -> bool:
        group = self._active_dialog_group()
        return group is not None and group in _CONTINUABLE_GROUPS

    def is_viewing_options(self) -> bool:
        return InterfaceID.CHATMENU in self._cache.active_interfaces

    def is_enter_input_open(self) -> bool:
        w = Widget(InterfaceID.Chatbox.INPUT)
        w.enable(WidgetFields.is_hidden)
        w.enable(WidgetFields.get_text)
        result = w.get()
        if result.get("is_hidden", True):
            return False
        text = result.get("text", "")
        return "Grand Exchange" not in text

    def get_text(self) -> str:
        group = self._active_dialog_group()
        if group is None:
            return ""
        widget_id = _TEXT_WIDGETS.get(group)
        if widget_id is None:
            return ""
        w = Widget(widget_id)
        w.enable(WidgetFields.get_text)
        result = w.get()
        return result.get("text", "")

    def get_name(self) -> str:
        group = self._active_dialog_group()
        if group is None:
            return ""
        widget_id = _NAME_WIDGETS.get(group)
        if widget_id is None:
            return ""
        w = Widget(widget_id)
        w.enable(WidgetFields.get_text)
        result = w.get()
        return result.get("text", "")

    def get_options(self) -> list[str]:
        if not self.is_viewing_options():
            return []
        w = Widget(InterfaceID.Chatmenu.OPTIONS)
        w.enable(WidgetFields.get_text)
        children = w.get_children()
        return [c["text"] for c in children if c.get("text")]

    def continue_dialog(self) -> None:
        self._keyboard.press_space()

    def choose_option(self, option: str | int) -> bool:
        if isinstance(option, int):
            if not 1 <= option <= 9:
                return False
            self._keyboard.press_number(option)
            return True
        options = self.get_options()
        for i, text in enumerate(options, start=1):
            if option.lower() in text.lower():
                self._keyboard.press_number(i)
                return True
        return False

    def enter_amount(self, amount: int) -> None:
        self._keyboard.type(str(amount))
        self._keyboard.press_enter()

    def enter_text(self, text: str) -> None:
        self._keyboard.type(text)
        self._keyboard.press_enter()
