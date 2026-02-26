from __future__ import annotations

from typing import TYPE_CHECKING

import escape.timing as timing
from escape._logger import logger
from escape.bt.actions import Status
from escape.navigation.click import Click
from escape.point import Point

if TYPE_CHECKING:
    from escape.pathfinder import Transport


def _extract_code(name: str) -> str | None:
    """Extract 3-letter fairy ring code from transport name.

    "Fairy ring A I Q" → "AIQ"
    "D K R" → "DKR"
    """
    prefix = "Fairy ring "
    if name.startswith(prefix):
        return name[len(prefix):].replace(" ", "")
    code = name.replace(" ", "")
    if len(code) == 3 and code.isalpha():
        return code
    return None


class FairyRingSolver:
    """Transport solver: use a fairy ring to teleport via code."""

    def __init__(self) -> None:
        self._clicker: Click | None = None

    def reset(self) -> None:
        if self._clicker is not None:
            self._clicker.reset()
        self._clicker = None

    def solve(self, transport: Transport) -> Status:
        if self._clicker is None:
            code = _extract_code(transport.name)
            if code is None:
                logger.warning("fairy-solver: cannot extract code from '{}'", transport.name)
                return Status.FAILURE

            def use_fairy_ring() -> bool:
                from escape.fairy_ring import FairyRingInterface
                from escape.objects import Objects

                fairy_ring = FairyRingInterface()
                objects = Objects()

                if fairy_ring.is_last_destination(code):
                    option = f"Last-destination ({code})"
                    logger.debug("fairy-solver: using last-destination '{}'", option)
                    obj = objects.nearest(
                        names=["Fairy ring", "Spiritual fairy tree"],
                    )
                    return obj is not None and obj.interact(option)

                logger.debug("fairy-solver: configuring code '{}'", code)
                obj = objects.nearest(
                    names=["Fairy ring", "Spiritual fairy tree"],
                )
                if obj is None or not obj.interact("Configure"):
                    logger.warning("fairy-solver: failed to click Configure")
                    return False

                if not timing.wait_until(fairy_ring.is_open, timeout=5):
                    logger.warning("fairy-solver: fairy ring interface did not open")
                    return False

                return fairy_ring.interact(code)

            duration = transport.metadata[0].duration_ticks if transport.metadata else 0
            self._clicker = Click(
                click=use_fairy_ring,
                is_complete=lambda: self._near_destination(transport),
                timeout_ticks=3 + duration,
                name=f"fairy-{code}",
            )

        return self._clicker.tick()

    def _near_destination(self, transport: Transport) -> bool:
        from escape._services import Services

        cache = Services.get().cache
        pos = cache.world_position
        return pos is not None and transport.destination.is_nearby(Point(*pos), 5)
