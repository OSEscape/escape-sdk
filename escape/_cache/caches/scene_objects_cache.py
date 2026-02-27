from __future__ import annotations

from typing import TYPE_CHECKING

from escape.objects import SceneObject

if TYPE_CHECKING:
    from escape._proto.bridge.v1.bridge_pb2 import (  # pyright: ignore[reportMissingImports]
        SceneObjectsUpdate,
    )


class SceneObjectCache:
    def __init__(self):
        self.objects: list[SceneObject] = []
        self._stub = None
        self._streamed_ids: set[int] = set()
        self._streamed_names: set[str] = set()
        self._stream_all: bool = False

    def set_stub(self, stub) -> None:
        self._stub = stub

    def process_update(self, update: SceneObjectsUpdate) -> None:
        self.objects = [SceneObject.from_proto(obj) for obj in update.objects]

    def ensure_streamed(
        self,
        ids: list[int] | None = None,
        names: list[str] | None = None,
    ) -> None:
        if self._stream_all:
            return

        new_ids = set(ids) - self._streamed_ids if ids else set()
        new_names = {n.lower() for n in names} - self._streamed_names if names else set()

        if not new_ids and not new_names:
            return

        assert self._stub is not None

        from escape._proto.bridge.v1 import bridge_pb2

        request = bridge_pb2.StreamObjectsRequest(
            ids=list(new_ids),
            names=list(new_names),
        )
        response = self._stub.StreamObjects(request)
        self.process_update(response)

        self._streamed_ids.update(new_ids)
        self._streamed_names.update(new_names)

    def ensure_stream_all(self) -> None:
        if self._stream_all:
            return

        assert self._stub is not None

        from escape._proto.bridge.v1 import bridge_pb2

        request = bridge_pb2.StreamObjectsRequest(stream_all=True)
        response = self._stub.StreamObjects(request)
        self.process_update(response)
        self._stream_all = True

    def clear_subscriptions(self) -> None:
        self._streamed_ids.clear()
        self._streamed_names.clear()
        self._stream_all = False
        self.objects.clear()
