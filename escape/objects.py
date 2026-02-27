from __future__ import annotations

from dataclasses import dataclass, replace

from escape._math import _chebyshev
from escape._models import EntityType


@dataclass(frozen=True, slots=True)
class SceneObject:
    type: int
    id: int
    packed_location: int
    orientation: int
    size_x: int
    size_y: int
    name: str
    actions: tuple[str, ...]
    distance: int = -1

    @classmethod
    def from_proto(cls, proto) -> SceneObject:
        return cls(
            type=proto.type,
            id=proto.id,
            packed_location=proto.packed_location,
            orientation=proto.orientation,
            size_x=proto.size_x,
            size_y=proto.size_y,
            name=proto.name,
            actions=tuple(proto.actions),
        )

    @property
    def entity_type(self) -> EntityType:
        return EntityType.OBJECT

    def interact(self, option: str | None = None) -> bool:
        import escape.timing as timing
        from escape._logger import logger
        from escape._services import Services

        logger.debug(
            "interact: picked id={} name='{}' pos=({},{}) dist={} actions={}",
            self.id,
            self.name,
            self.world_x,
            self.world_y,
            self.distance,
            self.actions,
        )
        tracker = Services.get().tracker
        tracker.track_object(self.packed_location, self.id)
        try:
            if not timing.wait_until(lambda: tracker.target_exists, timeout=1.0):
                logger.warning("Timeout waiting for object clickbox")
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
    def sw_x(self) -> int:
        return self.world_x - self.size_x // 2

    @property
    def sw_y(self) -> int:
        return self.world_y - self.size_y // 2

    @property
    def tiles(self) -> list[tuple[int, int, int]]:
        """All tiles occupied by this object. Sizes are pre-adjusted by Java."""
        return [
            (self.sw_x + dx, self.sw_y + dy, self.plane)
            for dx in range(self.size_x)
            for dy in range(self.size_y)
        ]

    @property
    def position(self) -> tuple[int, int, int]:
        return (self.world_x, self.world_y, self.plane)


class Objects:
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
        option: list[str] | None = None,
        plane: int | None = None,
    ) -> list[SceneObject]:
        if ids or names:
            self._cache.ensure_objects_streamed(ids, names)
        else:
            self._cache.ensure_all_objects_streamed()
        result = self._cache.scene_objects
        if ids:
            id_set = set(ids)
            result = [o for o in result if o.id in id_set]
        if names:
            name_set = {n.lower() for n in names}
            result = [o for o in result if o.name.lower() in name_set]
        if option:
            option_set = set(option)
            result = [o for o in result if option_set.intersection(o.actions)]
        if plane is not None:
            result = [o for o in result if o.plane == plane]
        px, py, _ = self._cache.world_position
        result = [replace(o, distance=_chebyshev(o.world_x, o.world_y, px, py)) for o in result]
        if max_distance > 0:
            result = [o for o in result if o.distance <= max_distance]
        return result

    def get_all(self) -> list[SceneObject]:
        """One-time snapshot of all scene objects without affecting streaming subscriptions."""
        from google.protobuf.empty_pb2 import Empty

        response = self._stub.GetAllObjects(Empty())
        px, py, _ = self._cache.world_position
        return [
            replace(
                SceneObject.from_proto(o),
                distance=_chebyshev(
                    o.packed_location & 0x7FFF, (o.packed_location >> 15) & 0x7FFF, px, py
                ),
            )
            for o in response.objects
        ]

    def stream_all(self) -> None:
        """Subscribe to streaming updates for all scene objects."""
        self._cache.ensure_all_objects_streamed()

    def nearest(
        self,
        ids: list[int] | None = None,
        names: list[str] | None = None,
        max_distance: int = 0,
        options: list[str] | None = None,
        plane: int | None = None,
    ) -> SceneObject | None:
        results = self.get(
            ids=ids, names=names, max_distance=max_distance, option=options, plane=plane
        )
        if not results:
            return None
        return min(results, key=lambda o: o.distance)
