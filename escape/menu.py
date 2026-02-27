"""Menu module - handles right-click context menu interactions."""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

import escape.timing as timing
from escape._logger import logger
from escape.geometry import Box

if TYPE_CHECKING:
    from escape._cache.processed_cache import ProcessedCache, SubMenuSort
    from escape.input import Mouse


class Menu:
    def __init__(self, cache: ProcessedCache, mouse: Mouse):
        self._cache = cache
        self._mouse = mouse

    @staticmethod
    def _match_option(option_text: str, full_option: str) -> bool:
        full_lower = full_option.lower()
        option_lower = option_text.lower()
        if full_lower == option_lower:
            return True
        return full_lower.startswith(option_lower) and full_lower[len(option_lower)] == " "

    def is_open(self) -> bool:
        state = self._cache.menu_open_state
        return state.menu_open if state else False

    def _get_options(self) -> tuple[list[str], list[str]]:
        data = self._cache.menu_options
        if data is None:
            return [], []

        menu_actions = list(data.menu_actions) if data.menu_actions else []
        options = list(data.options) if data.options else []
        targets = list(data.targets) if data.targets else []

        if not menu_actions or not options or not targets:
            return [], []

        formatted_options = [
            f"{option} {target}".strip() for option, target in zip(options, targets, strict=False)
        ]

        return formatted_options, menu_actions

    def _get_menu_info(self):
        return self._cache.menu_open_state

    def wait_has_menu_action(self, menu_action: str, ticks: int = 2) -> bool:
        """Wait up to *ticks* game ticks for a menu action to appear."""
        return timing.wait_until_ticks(
            lambda: self.has_menu_action(menu_action),
            ticks=ticks,
        )

    def wait_has_option(self, option: str, ticks: int = 2) -> bool:
        """Wait up to *ticks* game ticks for a menu option to appear."""
        return timing.wait_until_ticks(
            lambda: self.has_option(option),
            ticks=ticks,
        )

    def open(self, timeout: float = 0.5) -> bool:
        if self.is_open():
            return True

        self._mouse.right_click()

        return timing.wait_until(self.is_open, timeout=timeout, poll_interval=0.001)

    def close(self, use_cancel: bool = True, timeout: float = 1.0) -> bool:
        if not self.is_open():
            return True

        state = self._get_menu_info()
        if state is None:
            return True

        scrollable = state.scrollable
        menu_x = state.menu_x
        menu_y = state.menu_y
        menu_width = state.menu_width
        menu_height = state.menu_height

        if scrollable:
            use_cancel = False

        if use_cancel and not scrollable:
            options = self.get_options()
            cancel_index = None

            for i, option in enumerate(options):
                if "cancel" in option.lower():
                    cancel_index = i
                    break

            if cancel_index is not None:
                box = self.get_option_box(cancel_index)
                if box:
                    pt = box.random_point()
                    self._mouse.click_at(pt.x, pt.y)
                    return timing.wait_until(
                        lambda: not self.is_open(), timeout=timeout, poll_interval=0.001
                    )
                use_cancel = False
            else:
                use_cancel = False

        if not use_cancel:
            menu_x1 = menu_x
            menu_y1 = menu_y
            menu_x2 = menu_x + menu_width
            menu_y2 = menu_y + menu_height

            distance = random.randint(30, 50)
            direction = random.choice(["up", "down", "left", "right"])

            if direction == "up":
                target_x = random.randint(menu_x1, menu_x2)
                target_y = menu_y1 - distance
            elif direction == "down":
                target_x = random.randint(menu_x1, menu_x2)
                target_y = menu_y2 + distance
            elif direction == "left":
                target_x = menu_x1 - distance
                target_y = random.randint(menu_y1, menu_y2)
            else:
                target_x = menu_x2 + distance
                target_y = random.randint(menu_y1, menu_y2)

            self._mouse.move_to(target_x, target_y)

            return timing.wait_until(
                lambda: not self.is_open(), timeout=timeout, poll_interval=0.001
            )

        return timing.wait_until(lambda: not self.is_open(), timeout=timeout, poll_interval=0.001)

    def get_options(self) -> list[str]:
        menu_options, _ = self._get_options()
        return menu_options

    def get_menu_actions(self) -> list[str]:
        _, menu_actions = self._get_options()
        return menu_actions

    def get_left_click_option(self) -> str | None:
        options = self.get_options()
        return options[0] if options else None

    def get_left_click_action(self) -> str | None:
        menu_actions = self.get_menu_actions()
        return menu_actions[0] if menu_actions else None

    def has_option(self, option_text: str) -> bool:
        options = self.get_options()
        return any(self._match_option(option_text, option) for option in options)

    def has_menu_action(self, menu_action: str) -> bool:
        menu_actions = self.get_menu_actions()
        menu_action_lower = menu_action.lower()
        return any(menu_action_lower in a.lower() for a in menu_actions)

    def get_option_box(self, option_index: int) -> Box | None:
        if not self.is_open():
            return None

        state = self._get_menu_info()
        if state is None:
            return None

        menu_x = state.menu_x
        menu_y = state.menu_y
        menu_width = state.menu_width

        option_x = menu_x + 2
        option_y = menu_y + 19 + (option_index * 15)

        return Box(option_x, option_y, menu_width - 5, 14)

    def hover_option(self, option_text: str) -> bool:
        if not self.open():
            return False

        options = self.get_options()

        for i, option in enumerate(options):
            if self._match_option(option_text, option):
                box = self.get_option_box(i)
                if box:
                    pt = box.random_point()
                    self._mouse.move_to(pt.x, pt.y, linear=True)
                    return True

        return False

    def hover_option_index(self, option_index: int) -> bool:
        if not self.open():
            return False

        box = self.get_option_box(option_index)
        if box:
            pt = box.random_point()
            self._mouse.move_to(pt.x, pt.y, linear=True)
            return True
        return False

    def wait_menu_click_event(self, max_age: float = 0.2, timeout: float = 0.5) -> bool:
        if self._cache.menu_click_fresh:
            click = self._cache.latest_menu_click
            if click and (time.time() - click.timestamp) < max_age:
                return True

        click = self._cache.latest_menu_click
        initial_timestamp = click.timestamp if click else 0

        def check_event(ts) -> bool:
            current_click = self._cache.latest_menu_click
            current_timestamp = current_click.timestamp if current_click else 0
            return (current_timestamp - ts) > 0

        return timing.wait_until(
            lambda: check_event(initial_timestamp), timeout=timeout, poll_interval=0.001
        )

    def last_option_clicked(self) -> str:
        click = self._cache.latest_menu_click
        if not click:
            return ""

        return f"{click.menu_option} {click.menu_target}".strip()

    def wait_option_clicked(
        self, option_text: str, max_age: float = 0.2, timeout: float = 0.5
    ) -> bool:
        if not self.wait_menu_click_event(max_age=max_age, timeout=timeout):
            return False

        self._cache.consume_menu_click()

        return self._match_option(option_text, self.last_option_clicked())

    def wait_menu_closed(self, timeout: float = 0.5) -> bool:
        return timing.wait_until(lambda: not self.is_open(), timeout=timeout, poll_interval=0.001)

    def click_option(self, option_text: str) -> bool:
        logger.debug(f"Menu.click_option: {option_text}")

        if self.is_open():
            if self.has_option(option_text):
                self.hover_option(option_text)
                self._mouse.left_click()
                return self.wait_option_clicked(option_text) and self.wait_menu_closed()
            sub_match = self._find_in_sub_menu(option_text)
            if sub_match is not None:
                return self._click_sub_menu_option(*sub_match, option_text)
            return False

        left_click_option = self.get_left_click_option()
        if left_click_option is None:
            return False

        if self._match_option(option_text, left_click_option):
            self._mouse.left_click()
            return self.wait_option_clicked(option_text)

        if self.has_option(option_text):
            self.open()
            self.hover_option(option_text)
            self._mouse.left_click()
            return self.wait_option_clicked(option_text) and self.wait_menu_closed()

        sub_match = self._find_in_sub_menu(option_text)
        if sub_match is not None:
            if not self.open():
                return False
            return self._click_sub_menu_option(*sub_match, option_text)

        return False

    def click_option_index(self, option_index: int) -> bool:
        if not self.open():
            return False

        box = self.get_option_box(option_index)
        if box:
            pt = box.random_point()
            self._mouse.click_at(pt.x, pt.y)
            return True
        return False

    def click_option_action(self, menu_action: str) -> bool:
        options, menu_actions = self._get_options()
        for i, action in enumerate(menu_actions):
            if menu_action.lower() in action.lower():
                return self.click_option(options[i])
        return False

    def has_sub_menu(self) -> bool:
        data = self._cache.menu_options
        return data is not None and len(data.sub_menus) > 0

    def get_sub_menu(self) -> SubMenuSort | None:
        data = self._cache.menu_options
        if data is None or not data.sub_menus:
            return None
        return data.sub_menus[0]

    def get_sub_menu_options(self) -> list[str]:
        sm = self.get_sub_menu()
        if sm is None:
            return []
        return [
            f"{option} {target}".strip()
            for option, target in zip(sm.options, sm.targets, strict=False)
        ]

    def _find_in_sub_menu(self, option_text: str) -> tuple[int, int] | None:
        """Find option in submenu. Returns (parent_index, sub_option_index) or None."""
        sm = self.get_sub_menu()
        if sm is None:
            return None
        sub_options = self.get_sub_menu_options()
        for i, option in enumerate(sub_options):
            if self._match_option(option_text, option):
                return (sm.parent_index, i)
        return None

    def get_sub_menu_option_box(self, sub_option_index: int) -> Box | None:
        state = self._get_menu_info()
        if state is None or not state.has_sub_menu or state.sub_menu_width <= 0:
            return None
        option_x = state.sub_menu_x + 2
        option_y = state.sub_menu_y + 19 + (sub_option_index * 15)
        return Box(option_x, option_y, state.sub_menu_width - 5, 14)

    def _click_sub_menu_option(
        self, parent_index: int, sub_option_index: int, option_text: str
    ) -> bool:
        if not self.is_open():
            if not self.open():
                return False

        box = self.get_option_box(parent_index)
        if not box:
            return False
        pt = box.random_point()
        self._mouse.move_to(pt.x, pt.y, linear=True)

        def sub_menu_visible() -> bool:
            state = self._get_menu_info()
            return state is not None and state.sub_menu_width > 0

        if not timing.wait_until(sub_menu_visible, timeout=0.5, poll_interval=0.001):
            return False

        sub_box = self.get_sub_menu_option_box(sub_option_index)
        if not sub_box:
            return False
        pt = sub_box.random_point()
        self._mouse.move_to(pt.x, pt.y, linear=True)
        self._mouse.left_click()
        return self.wait_option_clicked(option_text) and self.wait_menu_closed()
