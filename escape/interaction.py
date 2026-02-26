"""Universal interaction: move, validate, click, confirm."""

from __future__ import annotations

from escape._logger import logger
from time import sleep
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape.point import ScreenPoint


def hover(point: ScreenPoint, option: str | None = None, action: str | None = None) -> bool:
    """Move mouse to point."""
    from escape._services import Services

    services = Services.get()
    mouse = services.mouse
    menu = services.menu

    mouse.move_to(point.x, point.y)

    if option is not None:
        return menu.wait_has_option(option)
    if action is not None:
        return menu.wait_has_menu_action(action)
    return True


def right_click(point: ScreenPoint) -> None:
    """Right-click at point."""
    from escape._services import Services

    Services.get().mouse.right_click(point.x, point.y)


def interact(
    point: ScreenPoint | None = None,
    *,
    option: str | None = None,
    action: str | None = None,
    wait: bool = True,
) -> bool:
    """Universal interaction: move -> validate -> click -> confirm.

    Args:
        point: Screen point to move to before interacting.
        option: Menu option text to select (e.g. "Talk-to", "Bank").
        action: Menu action to select (e.g. "WALK", "NPC_FIRST_OPTION").
        wait: Whether to wait for option to appear (for game-world entities).

    Returns:
        True if the interaction succeeded, False otherwise.
        Raw clicks (no option/action) always return True.

    """
    from escape._services import Services

    services = Services.get()
    mouse = services.mouse
    menu = services.menu

    if point is not None:
        mouse.move_to(point.x, point.y)

    if action is not None:
        if not menu.wait_has_menu_action(action):
            logger.warning("Menu action '{}' not found after waiting", action)
            return False
        return menu.click_option_action(action)

    if option is not None:
        if wait and not menu.wait_has_option(option):
            logger.warning("Menu option '{}' not found after waiting", option)
            return False
        return menu.click_option(option)

    # Raw left click
    sleep(0.05)
    mouse.left_click()
    logger.debug(f"Performed raw left click at ({mouse.position[0]}, {mouse.position[1]})")
    return True
