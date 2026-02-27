from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import escape.timing as timing
from escape._resources import varps
from escape.constants import InterfaceID, VarbitID
from escape.gametab import GameTab, GameTabs
from escape.widget import Buttons

if TYPE_CHECKING:
    from escape.skills import Skills


class PrayerType(Enum):
    THICK_SKIN = 0
    BURST_OF_STRENGTH = 1
    CLARITY_OF_THOUGHT = 2
    ROCK_EYE = 3
    SUPERHUMAN_STRENGTH = 4
    IMPROVED_REFLEXES = 5
    RAPID_RESTORE = 6
    RAPID_HEAL = 7
    PROTECT_ITEM = 8
    STEEL_SKIN = 9
    ULTIMATE_STRENGTH = 10
    INCREDIBLE_REFLEXES = 11
    PROTECT_FROM_MAGIC = 12
    PROTECT_FROM_MISSILES = 13
    PROTECT_FROM_MELEE = 14
    RETRIBUTION = 15
    REDEMPTION = 16
    SMITE = 17
    SHARP_EYE = 18
    MYSTIC_WILL = 19
    HAWK_EYE = 20
    MYSTIC_LORE = 21
    EAGLE_EYE = 22
    MYSTIC_MIGHT = 23
    RIGOUR = 24
    CHIVALRY = 25
    PIETY = 26
    AUGURY = 27
    PRESERVE = 28


class Prayer(GameTabs):
    TAB_TYPE = GameTab.PRAYER

    def __init__(self, skills: Skills):
        super().__init__()
        self._skills = skills
        self.prayer_buttons = Buttons(
            InterfaceID.PRAYERBOOK,
            [
                InterfaceID.Prayerbook.PRAYER1,
                InterfaceID.Prayerbook.PRAYER2,
                InterfaceID.Prayerbook.PRAYER3,
                InterfaceID.Prayerbook.PRAYER4,
                InterfaceID.Prayerbook.PRAYER5,
                InterfaceID.Prayerbook.PRAYER6,
                InterfaceID.Prayerbook.PRAYER7,
                InterfaceID.Prayerbook.PRAYER8,
                InterfaceID.Prayerbook.PRAYER9,
                InterfaceID.Prayerbook.PRAYER10,
                InterfaceID.Prayerbook.PRAYER11,
                InterfaceID.Prayerbook.PRAYER12,
                InterfaceID.Prayerbook.PRAYER13,
                InterfaceID.Prayerbook.PRAYER14,
                InterfaceID.Prayerbook.PRAYER15,
                InterfaceID.Prayerbook.PRAYER16,
                InterfaceID.Prayerbook.PRAYER17,
                InterfaceID.Prayerbook.PRAYER18,
                InterfaceID.Prayerbook.PRAYER19,
                InterfaceID.Prayerbook.PRAYER20,
                InterfaceID.Prayerbook.PRAYER21,
                InterfaceID.Prayerbook.PRAYER22,
                InterfaceID.Prayerbook.PRAYER23,
                InterfaceID.Prayerbook.PRAYER24,
                InterfaceID.Prayerbook.PRAYER25,
                InterfaceID.Prayerbook.PRAYER26,
                InterfaceID.Prayerbook.PRAYER27,
                InterfaceID.Prayerbook.PRAYER28,
                InterfaceID.Prayerbook.PRAYER29,
            ],
            [
                "Thick Skin",
                "Burst of Strength",
                "Clarity of Thought",
                "Rock Skin",
                "Superhuman Strength",
                "Improved Reflexes",
                "Rapid Restore",
                "Rapid Heal",
                "Protect Item",
                "Steel Skin",
                "Ultimate Strength",
                "Incredible Reflexes",
                "Protect from Magic",
                "Protect from Missiles",
                "Protect from Melee",
                "Retribution",
                "Redemption",
                "Smite",
                "Sharp Eye",
                "Mystic Will",
                "Hawk Eye",
                "Mystic Lore",
                "Eagle Eye",
                "Mystic Might",
                "Rigour",
                "Chivalry",
                "Piety",
                "Augury",
                "Preserve",
            ],
        )

        self.quickprayer_orb = Buttons(
            InterfaceID.ORBS,
            [InterfaceID.Orbs.PRAYERBUTTON],
            ["Quick-prayers"],
        )

        self.close_quickprayer_button = Buttons(
            InterfaceID.QUICKPRAYER,
            [InterfaceID.Quickprayer.CLOSE],
            ["Done"],
        )

    def get_active_prayer_varbit(self) -> int | None:
        return varps.get_varbit(VarbitID.PRAYER_ALLACTIVE)

    def get_quick_prayer_varbit(self) -> int | None:
        return varps.get_varbit(VarbitID.QUICKPRAYER_SELECTED)

    def _prayers_from_bitmask(self, varbit_value: int) -> list[PrayerType]:
        return [p for p in PrayerType if (varbit_value & (1 << p.value)) != 0]

    def is_prayer_active(self, prayer: PrayerType) -> bool | None:
        varbit_value = self.get_active_prayer_varbit()
        if varbit_value is None:
            return None
        return (varbit_value & (1 << prayer.value)) != 0

    @property
    def active_prayers(self) -> list[PrayerType] | None:
        varbit_value = self.get_active_prayer_varbit()
        if varbit_value is None:
            return None
        return self._prayers_from_bitmask(varbit_value)

    def activate(self, prayer: PrayerType, safe: bool = True) -> bool:
        if not self.open():
            return False

        if not self.is_prayer_active(prayer) or not safe:
            return self.prayer_buttons.interact(self.prayer_buttons.names[prayer.value])
        return True

    def deactivate(self, prayer: PrayerType) -> bool:
        if not self.open():
            return False

        if self.is_prayer_active(prayer):
            return self.prayer_buttons.interact(self.prayer_buttons.names[prayer.value])
        return True

    def get_prayer_points(self) -> int:
        return self._skills.get_level("Prayer")

    @property
    def selected_quick_prayers(self) -> list[PrayerType] | None:
        varbit_value = self.get_quick_prayer_varbit()
        if varbit_value is None:
            return None
        return self._prayers_from_bitmask(varbit_value)

    def is_quick_prayer_active(self) -> bool | None:
        varbit_value = varps.get_varbit(VarbitID.QUICKPRAYER_ACTIVE)
        if varbit_value is None:
            return None
        return varbit_value == 1

    def activate_quick_prayer(self) -> bool:
        if not self.open():
            return False

        if not self.is_quick_prayer_active():
            return self.quickprayer_orb.interact("Quick-prayers")
        return True

    def deactivate_quick_prayer(self) -> bool:
        if not self.open():
            return False

        if self.is_quick_prayer_active():
            return self.quickprayer_orb.interact("Quick-prayers")
        return True

    def is_quick_prayer_setup_open(self) -> bool:
        return InterfaceID.QUICKPRAYER in self._cache.active_interfaces

    def open_quick_prayer_setup(self) -> bool:
        if InterfaceID.QUICKPRAYER in self._cache.active_interfaces:
            return True

        if self.quickprayer_orb.interact(menu_option="Setup"):
            return timing.wait_until(self.is_quick_prayer_setup_open, timeout=3.0)
        return False

    def close_quick_prayer_setup(self) -> bool:
        if not self.is_quick_prayer_setup_open():
            return True

        if self.close_quickprayer_button.interact("Done"):
            return timing.wait_until(lambda: not self.is_quick_prayer_setup_open(), timeout=3.0)
        return False

    def configure_quick_prayers(self, prayers: list[PrayerType]) -> bool:
        if not self.open_quick_prayer_setup():
            return False

        current_quick_prayers = set(self.selected_quick_prayers or [])
        prayer_set = set(prayers)

        should_activate = prayer_set.difference(current_quick_prayers)
        should_deactivate = current_quick_prayers.difference(prayer_set)

        for prayer in should_deactivate:
            if not self.prayer_buttons.interact(self.prayer_buttons.names[prayer.value]):
                return False
        if should_deactivate:
            timing.wait_ticks(1)

        for prayer in should_activate:
            if not self.prayer_buttons.interact(self.prayer_buttons.names[prayer.value]):
                return False
        if should_activate:
            timing.wait_ticks(1)

        return (
            self.close_quick_prayer_setup() and set(self.selected_quick_prayers or []) == prayer_set
        )
