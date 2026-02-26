"""Cache for storing menu option click events."""

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape._proto.bridge.v1.bridge_pb2 import (  # pyright: ignore[reportMissingImports]
        MenuOptionClickUpdate,
    )


@dataclass(frozen=True, slots=True)
class MenuOptionClick:
    """Represents a menu option click event."""

    menu_option: str
    menu_target: str
    id: int
    widget_id: int
    param0: int
    param1: int
    menu_action: str
    click_location: int  # Packed coordinate
    timestamp: float


class MenuOptionClickCache:
    def __init__(self):
        self.latest_click: MenuOptionClick | None = None
        self.fresh: bool = False

    def process_click(self, click: MenuOptionClickUpdate) -> None:
        """Process menu option click - stores latest click and sets fresh flag."""
        self.latest_click = MenuOptionClick(
            menu_option=click.menu_option,
            menu_target=click.menu_target,
            id=click.id,
            widget_id=click.widget_id,
            param0=click.param0,
            param1=click.param1,
            menu_action=click.menu_action,
            click_location=click.click_location,
            timestamp=time.time(),
        )
        self.fresh = True

    def get_latest_click(self) -> MenuOptionClick | None:
        """Get the latest click."""
        return self.latest_click

    def is_fresh(self) -> bool:
        """Check if a new click has arrived since last clear."""
        return self.fresh

    def clear_fresh(self) -> None:
        """Clear the fresh flag after consuming the click."""
        self.fresh = False
