from typing import TYPE_CHECKING

from escape.tile_items import GroundItem

if TYPE_CHECKING:
    from escape._proto.bridge.v1.bridge_pb2 import (  # pyright: ignore[reportMissingImports]
        GroundItemsUpdate,
    )


class GroundItemCache:
    def __init__(self):
        self.items: list[GroundItem] = []
        self._stub = None
        self._enabled: bool = False

    def set_stub(self, stub) -> None:
        self._stub = stub

    def process_update(self, update: GroundItemsUpdate) -> None:
        self.items = [GroundItem.from_proto(item) for item in update.ground_items]

    def ensure_enabled(self) -> None:
        if self._enabled:
            return

        assert self._stub is not None

        from google.protobuf.empty_pb2 import Empty

        response = self._stub.StreamGroundItems(Empty())
        self.process_update(response)
        self._enabled = True

    def clear_subscriptions(self) -> None:
        self._enabled = False
        self.items.clear()
