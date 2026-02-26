from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnimationEvent:
    actor_name: str
    animation_id: int
    packed_location: int

    @classmethod
    def from_proto(cls, proto) -> AnimationEvent:
        return cls(
            actor_name=proto.actor_name,
            animation_id=proto.animation_id,
            packed_location=proto.location,
        )


class AnimationCache:
    def __init__(self):
        self.by_actor: dict[str, int] = {}

    def process_change(self, proto_obj) -> None:
        self.by_actor[proto_obj.actor_name] = proto_obj.animation_id

    def get_animation(self, actor_name: str) -> int:
        return self.by_actor.get(actor_name, -1)
