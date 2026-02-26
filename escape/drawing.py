"""Drawing utility for rendering debug overlays on RuneLite."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import numpy as np
from google.protobuf.empty_pb2 import Empty
from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Generator

from escape._proto.bridge.v1 import bridge_pb2  # pyright: ignore[reportMissingImports]
from escape._transport import DIRECT_METADATA

# Maps DrawCommand oneof field name to the stub RPC method name.
_FIELD_TO_RPC = {
    "box": "AddBox",
    "circle": "AddCircle",
    "line": "AddLine",
    "polygon": "AddPolygon",
    "text": "AddText",
    "image": "AddImage",
}


class Drawing:
    """Drawing utility for rendering debug overlays on RuneLite."""

    def __init__(self, stub):
        self._stub = stub

    @staticmethod
    def _to_signed_int32(value: int) -> int:
        if value > 0x7FFFFFFF:
            return value - 0x100000000
        return value

    def _send(self, field: str, request) -> None:
        """Dispatch a draw command. Subclasses override for batching."""
        rpc = _FIELD_TO_RPC[field]
        getattr(self._stub, rpc)(request, metadata=DIRECT_METADATA)

    def add_box(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        argb_color: int,
        filled: bool,
        tag: str = "",
    ) -> None:
        """Draw a rectangle overlay."""
        self._send(
            "box",
            bridge_pb2.AddBoxRequest(
                x=x,
                y=y,
                width=width,
                height=height,
                argb_color=self._to_signed_int32(argb_color),
                filled=filled,
                tag=tag,
            ),
        )

    def add_circle(
        self,
        x: int,
        y: int,
        radius: int,
        argb_color: int,
        filled: bool,
        tag: str = "",
    ) -> None:
        """Draw a circle overlay."""
        self._send(
            "circle",
            bridge_pb2.AddCircleRequest(
                x=x,
                y=y,
                radius=radius,
                argb_color=self._to_signed_int32(argb_color),
                filled=filled,
                tag=tag,
            ),
        )

    def add_line(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        argb_color: int,
        thickness: int,
        tag: str = "",
    ) -> None:
        """Draw a line overlay."""
        self._send(
            "line",
            bridge_pb2.AddLineRequest(
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                argb_color=self._to_signed_int32(argb_color),
                thickness=thickness,
                tag=tag,
            ),
        )

    def add_polygon(
        self,
        x_points: list[int],
        y_points: list[int],
        argb_color: int,
        filled: bool,
        tag: str = "",
    ) -> None:
        """Draw a polygon overlay."""
        self._send(
            "polygon",
            bridge_pb2.AddPolygonRequest(
                x_points=x_points,
                y_points=y_points,
                argb_color=self._to_signed_int32(argb_color),
                filled=filled,
                tag=tag,
            ),
        )

    def add_text(
        self,
        text: str,
        x: int,
        y: int,
        argb_color: int,
        font_size: int = 0,
        tag: str = "",
    ) -> None:
        """Draw a text overlay."""
        self._send(
            "text",
            bridge_pb2.AddTextRequest(
                text=text,
                x=x,
                y=y,
                argb_color=self._to_signed_int32(argb_color),
                font_size=font_size,
                tag=tag,
            ),
        )

    def add_image(
        self,
        argb_pixels: list[int],
        img_width: int,
        img_height: int,
        x: int,
        y: int,
        tag: str = "",
    ) -> None:
        """Draw an image overlay from raw ARGB pixel data."""
        self._send(
            "image",
            bridge_pb2.AddImageRequest(
                argb_pixels=argb_pixels,
                img_width=img_width,
                img_height=img_height,
                x=x,
                y=y,
                tag=tag,
            ),
        )

    def add_image_from_path(
        self,
        path: str,
        x: int,
        y: int,
        tag: str = "",
    ) -> None:
        """Draw an image overlay loaded from a file path."""
        img = Image.open(path).convert("RGBA")
        pixels = np.array(img)

        argb = (
            (pixels[:, :, 3].astype(np.uint32) << 24)
            | (pixels[:, :, 0].astype(np.uint32) << 16)
            | (pixels[:, :, 1].astype(np.uint32) << 8)
            | pixels[:, :, 2].astype(np.uint32)
        )

        argb_signed = argb.astype(np.int32)

        width, height = img.size
        pixel_list = argb_signed.flatten().tolist()

        self.add_image(pixel_list, width, height, x, y, tag)

    def clear(self) -> None:
        """Clear all drawing overlays."""
        self._stub.ClearDrawing(Empty())

    def clear_tag(self, tag: str) -> None:
        """Clear all drawing overlays with the given tag."""
        req = bridge_pb2.ClearDrawingTagRequest(tag=tag)
        self._stub.ClearDrawingTag(req, metadata=DIRECT_METADATA)

    @contextmanager
    def batch(self, clear_tag: str = "") -> Generator[_BatchBuilder]:
        """Collect draw commands and send them in a single BatchDraw RPC.

        Usage:
            with client.drawing.batch(clear_tag="my_tag") as draw:
                draw.add_polygon(xs, ys, color, filled=False)
                draw.add_text("hello", x, y, WHITE)
        """
        builder = _BatchBuilder()
        yield builder
        req = bridge_pb2.BatchDrawRequest(
            commands=builder._commands,
            clear_tag=clear_tag,
        )
        self._stub.BatchDraw(req, metadata=DIRECT_METADATA)


class _BatchBuilder(Drawing):
    """Collects draw commands for batched submission."""

    def __init__(self) -> None:
        self._commands: list[bridge_pb2.DrawCommand] = []

    def _send(self, field: str, request) -> None:
        self._commands.append(bridge_pb2.DrawCommand(**{field: request}))
