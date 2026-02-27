from __future__ import annotations

from dataclasses import dataclass, replace

from escape._math import _chebyshev
from escape._models import EntityType

NOT_INTERACTING = -1
TARGET_LOCAL_PLAYER = -2
TARGET_OTHER_PLAYER = -3


@dataclass(frozen=True, slots=True)
class Npc:
    index: int
    id: int
    name: str
    world_x: int
    world_y: int
    plane: int
    animation: int
    pose_animation: int
    orientation: int
    combat_level: int
    is_dead: bool
    health_ratio: int
    health_scale: int
    interacting_index: int
    overhead_text: str
    actions: tuple[str, ...]
    size: int
    spot_anim_ids: tuple[int, ...]
    overhead_sprite_ids: tuple[int, ...]
    overhead_archive_ids: tuple[int, ...]
    distance: int = -1

    @classmethod
    def from_proto(cls, proto) -> Npc:
        return cls(
            index=proto.index,
            id=proto.id,
            name=proto.name,
            world_x=proto.world_x,
            world_y=proto.world_y,
            plane=proto.plane,
            animation=proto.animation,
            pose_animation=proto.pose_animation,
            orientation=proto.orientation,
            combat_level=proto.combat_level,
            is_dead=proto.is_dead,
            health_ratio=proto.health_ratio,
            health_scale=proto.health_scale,
            interacting_index=proto.interacting_index,
            overhead_text=proto.overhead_text,
            actions=tuple(proto.actions),
            size=proto.size,
            spot_anim_ids=tuple(proto.spot_anim_ids),
            overhead_sprite_ids=tuple(proto.overhead_sprite_ids),
            overhead_archive_ids=tuple(proto.overhead_archive_ids),
        )

    @property
    def entity_type(self) -> EntityType:
        return EntityType.NPC

    def interact(self, option: str | None = None) -> bool:
        import escape.timing as timing
        from escape._logger import logger
        from escape._services import Services

        tracker = Services.get().tracker
        tracker.track_npc(self.index)
        try:
            if not timing.wait_until(lambda: tracker.target_exists, timeout=1.0):
                logger.warning("Timeout waiting for npc clickbox")
                return False
            return tracker.click(option=option)
        finally:
            tracker.stop()

    @property
    def is_idle(self) -> bool:
        return self.animation == -1

    @property
    def is_animating(self) -> bool:
        return self.animation != -1

    @property
    def is_interacting(self) -> bool:
        return self.interacting_index != NOT_INTERACTING

    @property
    def is_targeting_local_player(self) -> bool:
        return self.interacting_index == TARGET_LOCAL_PLAYER

    @property
    def is_targeting_player(self) -> bool:
        return self.interacting_index <= TARGET_LOCAL_PLAYER

    @property
    def target_npc_index(self) -> int | None:
        return self.interacting_index if self.interacting_index >= 0 else None

    @property
    def health_percent(self) -> float | None:
        if self.health_scale <= 0:
            return None
        return (self.health_ratio / self.health_scale) * 100.0

    @property
    def position(self) -> tuple[int, int, int]:
        return (self.world_x, self.world_y, self.plane)


class Npcs:
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
        actions: list[str] | None = None,
        alive: bool | None = None,
        targeting_me: bool | None = None,
    ) -> list[Npc]:
        if ids or names:
            self._cache.ensure_npcs_streamed(ids, names)
        else:
            self._cache.ensure_all_npcs_streamed()
        result = self._cache.npcs
        if ids:
            id_set = set(ids)
            result = [n for n in result if n.id in id_set]
        if names:
            name_set = {n.lower() for n in names}
            result = [n for n in result if n.name.lower() in name_set]
        if actions:
            action_set = set(actions)
            result = [n for n in result if action_set.intersection(n.actions)]
        if alive is not None:
            result = [n for n in result if n.is_dead != alive]
        if targeting_me is not None:
            result = [n for n in result if n.is_targeting_local_player == targeting_me]
        px, py, _ = self._cache.world_position
        result = [replace(n, distance=_chebyshev(n.world_x, n.world_y, px, py)) for n in result]
        if max_distance > 0:
            result = [n for n in result if n.distance <= max_distance]
        return result

    def get_all(self) -> list[Npc]:
        """One-time snapshot of all NPCs without affecting streaming subscriptions."""
        from google.protobuf.empty_pb2 import Empty

        response = self._stub.GetAllNpcs(Empty())
        px, py, _ = self._cache.world_position
        return [
            replace(Npc.from_proto(n), distance=_chebyshev(n.world_x, n.world_y, px, py))
            for n in response.npcs
        ]

    def stream_all(self) -> None:
        """Subscribe to streaming updates for all NPCs."""
        self._cache.ensure_all_npcs_streamed()

    def nearest(
        self,
        ids: list[int] | None = None,
        names: list[str] | None = None,
        max_distance: int = 0,
        actions: list[str] | None = None,
        alive: bool | None = None,
        targeting_me: bool | None = None,
    ) -> Npc | None:
        results = self.get(
            ids=ids,
            names=names,
            max_distance=max_distance,
            actions=actions,
            alive=alive,
            targeting_me=targeting_me,
        )
        if not results:
            return None
        return min(results, key=lambda n: n.distance)

    def by_index(self, index: int) -> Npc | None:
        return self._cache.get_npc_by_index(index)
