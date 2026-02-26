from __future__ import annotations

from enum import Enum
from typing import ClassVar

import escape.timing as timing
from escape.constants import InterfaceID, VarbitID
from escape.widget import Buttons
from escape._resources import varps


class GameTab(Enum):
    COMBAT = 0
    SKILLS = 1
    PROGRESS = 2
    INVENTORY = 3
    EQUIPMENT = 4
    PRAYER = 5
    MAGIC = 6
    GROUPING = 7
    FRIENDS = 8
    ACCOUNT = 9
    LOGOUT = 10
    SETTINGS = 11
    EMOTES = 12
    MUSIC = 13

_FKEY_VARBITS = [
    VarbitID.STONE_COMBAT_KEY,
    VarbitID.STONE_STATS_KEY,
    VarbitID.STONE_JOURNAL_KEY,
    VarbitID.STONE_INV_KEY,
    VarbitID.STONE_WORN_KEY,
    VarbitID.STONE_PRAYER_KEY,
    VarbitID.STONE_MAGIC_KEY,
    VarbitID.STONE_CLANCHAT_KEY,
    VarbitID.STONE_FRIENDS_KEY,
    VarbitID.STONE_ACCOUNT_KEY,
    VarbitID.STONE_LOGOUT_KEY,
    VarbitID.STONE_OPTIONS1_KEY,
    VarbitID.STONE_OPTIONS2_KEY,
    VarbitID.STONE_MUSIC_KEY,
]

_ICON_IDS: dict[int, tuple[int, ...]] = {
    InterfaceID.TOPLEVEL: (
        InterfaceID.Toplevel.ICON0,
        InterfaceID.Toplevel.ICON1,
        InterfaceID.Toplevel.ICON2,
        InterfaceID.Toplevel.ICON3,
        InterfaceID.Toplevel.ICON4,
        InterfaceID.Toplevel.ICON5,
        InterfaceID.Toplevel.ICON6,
        InterfaceID.Toplevel.ICON7,
        InterfaceID.Toplevel.ICON9,  # this is intentional, don't change
        InterfaceID.Toplevel.ICON8,
        InterfaceID.Toplevel.ICON10,
        InterfaceID.Toplevel.ICON11,
        InterfaceID.Toplevel.ICON12,
        InterfaceID.Toplevel.ICON13,
    ),
    InterfaceID.TOPLEVEL_OSRS_STRETCH: (
        InterfaceID.ToplevelOsrsStretch.ICON0,
        InterfaceID.ToplevelOsrsStretch.ICON1,
        InterfaceID.ToplevelOsrsStretch.ICON2,
        InterfaceID.ToplevelOsrsStretch.ICON3,
        InterfaceID.ToplevelOsrsStretch.ICON4,
        InterfaceID.ToplevelOsrsStretch.ICON5,
        InterfaceID.ToplevelOsrsStretch.ICON6,
        InterfaceID.ToplevelOsrsStretch.ICON7,
        InterfaceID.ToplevelOsrsStretch.ICON9,
        InterfaceID.ToplevelOsrsStretch.ICON8,
        InterfaceID.ToplevelOsrsStretch.ICON10,
        InterfaceID.ToplevelOsrsStretch.ICON11,
        InterfaceID.ToplevelOsrsStretch.ICON12,
        InterfaceID.ToplevelOsrsStretch.ICON13,
    ),
    InterfaceID.TOPLEVEL_PRE_EOC: (
        InterfaceID.ToplevelPreEoc.ICON0,
        InterfaceID.ToplevelPreEoc.ICON1,
        InterfaceID.ToplevelPreEoc.ICON2,
        InterfaceID.ToplevelPreEoc.ICON3,
        InterfaceID.ToplevelPreEoc.ICON4,
        InterfaceID.ToplevelPreEoc.ICON5,
        InterfaceID.ToplevelPreEoc.ICON6,
        InterfaceID.ToplevelPreEoc.ICON7,
        InterfaceID.ToplevelPreEoc.ICON9,
        InterfaceID.ToplevelPreEoc.ICON8,
        InterfaceID.ToplevelPreEoc.ICON10,
        InterfaceID.ToplevelPreEoc.ICON11,
        InterfaceID.ToplevelPreEoc.ICON12,
        InterfaceID.ToplevelPreEoc.ICON13,
    ),
}


class GameTabs:
    TAB_TYPE: GameTab | None = None
    _tab_buttons: ClassVar[Buttons | None] = None

    def __init__(
        self,
        tab_type: GameTab | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        from escape._services import Services

        s = Services.get()
        self._cache = s.cache
        self._keyboard = s.keyboard
        if tab_type is not None:
            self.TAB_TYPE = tab_type

    def _get_tab_buttons(self) -> Buttons | None:
        if type(self)._tab_buttons is not None:
            return type(self)._tab_buttons
        active = set(self._cache.active_interfaces)
        for group_id, icon_ids in _ICON_IDS.items():
            if group_id in active:
                b = Buttons(group_id, list(icon_ids), [tab.name for tab in GameTab])
                b._set_boxes()
                type(self)._tab_buttons = b
                return b
        return None

    def _get_open_tab(self) -> GameTab | None:
        from escape.constants import VarClientID

        index = self._cache.get_varc(VarClientID.TOPLEVEL_PANEL)
        if isinstance(index, int) and index in GameTab._value2member_map_:
            return GameTab(index)
        return None

    def is_open(self) -> bool:
        return self._get_open_tab() == self.TAB_TYPE

    def open(self, use_fkeys: bool = True) -> bool:
        if self.is_open():
            return True

        if self.TAB_TYPE is None:
            raise NotImplementedError("Subclass must set TAB_TYPE")
        

        key = varps.get_varbit(_FKEY_VARBITS[self.TAB_TYPE.value])
        if use_fkeys and key:
            self._keyboard.press(_map_key(key))
            return timing.wait_until(self.is_open, timeout=0.5, poll_interval=0.001)
        else:
            buttons = self._get_tab_buttons()
            if not buttons:
                return False
            box = buttons.boxes[self.TAB_TYPE.value]
            if box:
                box.interact()
                return timing.wait_until(self.is_open, timeout=0.1, poll_interval=0.001)
        return False
    
def _map_key(key: int) -> str:
    if key <= 12:
        return f"F{key}"
    else:
        return "ESC"
