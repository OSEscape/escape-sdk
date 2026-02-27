from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from escape._logger import logger
from escape.bt.actions import Status
from escape.navigation.click import Click
from escape.point import Point

if TYPE_CHECKING:
    from escape.pathfinder import Transport


class TransportClickSolver:
    """Transport solver: click object from metadata, wait for arrival."""

    def __init__(self) -> None:
        self._clicker: Click | None = None
        self._arrival_threshold: int = -1

    def reset(self) -> None:
        if self._clicker is not None:
            self._clicker.reset()
        self._clicker = None
        self._arrival_threshold = -1

    def solve(self, transport: Transport) -> Status:
        if self._clicker is None:
            self._arrival_threshold = self._calculate_arrival_threshold(transport)
            duration = transport.metadata[0].duration_ticks if transport.metadata else 0
            self._clicker = Click(
                click=self._build_click_fn(transport),
                is_complete=lambda: self._near_destination(transport),
                timeout_ticks=3 + duration,
                name=f"transport-click-{transport.name}",
            )
            logger.debug("solver: threshold={} for '{}'", self._arrival_threshold, transport.name)

        return self._clicker.tick()

    def _build_click_fn(self, transport: Transport) -> Callable[[], bool]:
        """Build click callable from transport metadata. Runs once per solve cycle."""
        option, name, obj_id = self._parse_object_metadata(transport)
        plane = transport.origin.plane
        options = [option] if option else None

        def click() -> bool:
            from escape.objects import Objects

            logger.debug("solver: clicking '{}' option='{}' id={}", name, option, obj_id)
            objects = Objects()
            if obj_id is not None:
                obj = objects.nearest(ids=[obj_id], options=options, plane=plane)
                if obj is not None and obj.interact(option):
                    logger.debug("solver: clicked '{}' by id successfully", name)
                    return True
                logger.debug("solver: id {} miss, falling back to name '{}'", obj_id, name)
            if name is not None:
                obj = objects.nearest(names=[name], options=options, plane=plane)
                if obj is not None and obj.interact(option):
                    logger.debug("solver: clicked '{}' by name successfully", name)
                    return True
                return False
            logger.debug("solver: click failed for '{}'", name)
            return False

        return click

    def _near_destination(self, transport: Transport) -> bool:
        from escape._services import Services

        cache = Services.get().cache
        pos = cache.world_position
        near = pos is not None and transport.destination.is_nearby(
            Point(*pos), self._arrival_threshold
        )
        logger.debug(
            "solver | pos={} dest={} near={}",
            pos,
            transport.destination,
            near,
        )
        return near

    def _parse_object_metadata(
        self, transport: Transport
    ) -> tuple[str | None, str | None, int | None]:
        """Extract object interaction metadata from the transport."""
        if not transport.metadata:
            full_name = transport.name
        else:
            meta = transport.metadata[0]
            full_name = meta.action if meta.action else meta.name

        segments = full_name.split(" ")

        if not segments:
            return None, None, None

        menu_option = segments[0]

        obj_id: int | None = None
        if segments[-1].isdigit():
            obj_id = int(segments[-1])
        name = " ".join(segments[1:-1]) if len(segments) > 2 else None

        return menu_option, name, obj_id

    def _calculate_arrival_threshold(self, transport: Transport) -> int:
        """Calculate a reasonable arrival threshold based on transport metadata."""
        _distance = (
            transport.origin.distance_to(transport.destination)
            + abs(transport.destination.plane - transport.origin.plane) * 1000
        )
        return max(1, int(_distance * 0.25))


# Backwards-compatible alias
ObjectClickSolver = TransportClickSolver
