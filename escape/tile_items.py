from __future__ import annotations

from dataclasses import dataclass, replace

from escape._math import _chebyshev
from escape._models import EntityType


class Ownership:
    NONE = 0
    SELF = 1
    OTHER = 2
    GROUP = 3


@dataclass(frozen=True, slots=True)
class GroundItem:
    id: int
    quantity: int
    name: str
    packed_location: int
    ownership: int
    distance: int = -1

    @classmethod
    def from_proto(cls, proto) -> GroundItem:
        return cls(
            id=proto.id,
            quantity=proto.quantity,
            name=proto.name,
            packed_location=proto.packed_location,
            ownership=proto.ownership,
        )

    @property
    def entity_type(self) -> EntityType:
        return EntityType.ITEM

    def interact(self, option: str | None = None) -> bool:
        import escape.timing as timing
        from escape._logger import logger
        from escape._services import Services

        tracker = Services.get().tracker
        tracker.track_ground_item(self.packed_location, self.id)
        try:
            if not timing.wait_until(lambda: tracker.target_exists, timeout=1.0):
                logger.warning("Timeout waiting for ground item clickbox")
                return False
            return tracker.click(option=option)
        finally:
            tracker.stop()

    @property
    def world_x(self) -> int:
        return self.packed_location & 0x7FFF

    @property
    def world_y(self) -> int:
        return (self.packed_location >> 15) & 0x7FFF

    @property
    def plane(self) -> int:
        return (self.packed_location >> 30) & 0x3

    @property
    def position(self) -> tuple[int, int, int]:
        return (self.world_x, self.world_y, self.plane)

    @property
    def is_yours(self) -> bool:
        return self.ownership in (Ownership.SELF, Ownership.GROUP)

    @property
    def can_loot(self) -> bool:
        return self.ownership in (Ownership.NONE, Ownership.SELF, Ownership.GROUP)

    @property
    def is_public(self) -> bool:
        return self.ownership == Ownership.NONE


class TileItems:
    def __init__(self) -> None:
        from escape._services import Services

        s = Services.get()
        self._cache = s.cache
        self._stub = s.stub

    def get(
        self,
        ids: list[int] | None = None,
        names: list[str] | None = None,
        max_distance: int = 0,
        lootable: bool | None = None,
    ) -> list[GroundItem]:
        self._cache.ensure_ground_items_enabled()
        result = self._cache.ground_items
        if ids:
            id_set = set(ids)
            result = [i for i in result if i.id in id_set]
        if names:
            name_set = {n.lower() for n in names}
            result = [i for i in result if i.name.lower() in name_set]
        if lootable is not None:
            result = [i for i in result if i.can_loot == lootable]
        px, py, _ = self._cache.world_position
        result = [replace(i, distance=_chebyshev(i.world_x, i.world_y, px, py)) for i in result]
        if max_distance > 0:
            result = [i for i in result if i.distance <= max_distance]
        return result

    def get_all(self) -> list[GroundItem]:
        """One-time snapshot of all ground items without affecting streaming subscriptions."""
        from google.protobuf.empty_pb2 import Empty

        response = self._stub.GetAllGroundItems(Empty())
        px, py, _ = self._cache.world_position
        return [
            replace(
                GroundItem.from_proto(i),
                distance=_chebyshev(
                    i.packed_location & 0x7FFF, (i.packed_location >> 15) & 0x7FFF, px, py
                ),
            )
            for i in response.ground_items
        ]

    def stream(self) -> None:
        """Enable streaming updates for ground items."""
        self._cache.ensure_ground_items_enabled()

    def nearest(
        self,
        ids: list[int] | None = None,
        names: list[str] | None = None,
        max_distance: int = 0,
        lootable: bool | None = None,
    ) -> GroundItem | None:
        results = self.get(ids=ids, names=names, max_distance=max_distance, lootable=lootable)
        if not results:
            return None
        return min(results, key=lambda i: i.distance)
