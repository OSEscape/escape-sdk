"""Widget types for querying and interacting with game UI elements."""

import re
import time
import typing
from typing import ClassVar

from escape._proto.bridge.v1 import bridge_pb2
from escape._transport import DIRECT_METADATA
from escape.constants._widgetfields import WidgetField, WidgetFields

if typing.TYPE_CHECKING:
    from escape.geometry import Box


class Widget:
    """Query builder for fetching widget properties from the game client.

    Each widget is identified by a RuneLite widget ID. Enable specific
    property fields via ``enable()`` to build a bitmask, then call
    ``get()``, ``get_children()``, or the batch variants to fetch only
    the requested fields in a single gRPC call.
    """

    _FIELD_BITS: ClassVar[dict[str, int]] = {
        name.lower().replace("widget_prop_", ""): 1 << (val - 1)
        for name, val in bridge_pb2.WidgetProperty.items()
        if val > 0
    }
    _stub: ClassVar[typing.Any] = None

    def __init__(self, id: int):
        self._mask = 0
        self.id = id

    @property
    def mask(self) -> int:
        return self._mask

    def enable(self, field: WidgetField) -> Widget:
        key = self._camel_to_snake(field).removeprefix("get_").removesuffix("_listener")
        self._mask |= self._FIELD_BITS[key]
        return self

    def disable(self, field: WidgetField) -> Widget:
        key = self._camel_to_snake(field).removeprefix("get_").removesuffix("_listener")
        self._mask &= ~self._FIELD_BITS[key]
        return self

    def clear(self) -> Widget:
        self._mask = 0
        return self

    def enable_all(self) -> Widget:
        self._mask = (1 << len(self._FIELD_BITS)) - 1
        return self

    @classmethod
    def from_names(cls, widget_id: int, *fields: WidgetField) -> Widget:
        w = cls(widget_id)
        for f in fields:
            w.enable(f)
        return w

    def as_dict(self) -> dict[str, bool]:
        return {name: bool(self._mask & bit) for name, bit in self._FIELD_BITS.items()}

    def _use_direct_execution(self) -> bool:
        """Return True when the RPC can skip ClientThread dispatch.

        Widget lookups that don't request parent references are safe to
        execute directly, avoiding a thread hop on the Java side.
        """
        parent_fields = self._FIELD_BITS.get("parent", 0) | self._FIELD_BITS.get("parent_id", 0)
        return (self._mask & parent_fields) == 0

    @staticmethod
    def _camel_to_snake(name: str) -> str:
        name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
        return name.lower()

    @staticmethod
    def _convert_widget_response(widget_response) -> dict[str, typing.Any]:
        """Convert a proto WidgetResponse into a plain dict with snake_case keys."""
        result = {}
        for key, widget_value in widget_response.values.items():
            snake_key = Widget._camel_to_snake(key)
            if widget_value.HasField("single_value"):
                data_value = widget_value.single_value
                if data_value.HasField("i32"):
                    result[snake_key] = data_value.i32
                elif data_value.HasField("i64"):
                    result[snake_key] = data_value.i64
                elif data_value.HasField("str"):
                    result[snake_key] = data_value.str
                elif data_value.HasField("b"):
                    result[snake_key] = data_value.b
                elif data_value.HasField("rectangle"):
                    rect = data_value.rectangle
                    result[snake_key] = {
                        "x": rect.x,
                        "y": rect.y,
                        "width": rect.width,
                        "height": rect.height,
                    }
                elif data_value.HasField("point"):
                    point = data_value.point
                    result[snake_key] = {"x": point.x, "y": point.y}
            elif widget_value.HasField("multiple_values"):
                values_list = []
                for data_value in widget_value.multiple_values.values:
                    if data_value.HasField("i32"):
                        values_list.append(data_value.i32)
                    elif data_value.HasField("i64"):
                        values_list.append(data_value.i64)
                    elif data_value.HasField("str"):
                        values_list.append(data_value.str)
                    elif data_value.HasField("b"):
                        values_list.append(data_value.b)
                    elif data_value.HasField("rectangle"):
                        rect = data_value.rectangle
                        values_list.append(
                            {
                                "x": rect.x,
                                "y": rect.y,
                                "width": rect.width,
                                "height": rect.height,
                            }
                        )
                    elif data_value.HasField("point"):
                        point = data_value.point
                        values_list.append({"x": point.x, "y": point.y})
                result[snake_key] = values_list
        return result

    @classmethod
    def _get_stub(cls):
        if cls._stub is None:
            raise RuntimeError("Widget not initialized — call client.connect() first")
        return cls._stub

    def get(self) -> dict[str, typing.Any]:
        stub = Widget._get_stub()
        request = bridge_pb2.GetWidgetRequest(widget_id=self.id, mask=self.mask)
        response = stub.GetWidgetProperties(
            request, metadata=DIRECT_METADATA if self._use_direct_execution() else None
        )
        return self._convert_widget_response(response.widget)

    def get_child(self, child_index: int) -> dict[str, typing.Any]:
        stub = Widget._get_stub()
        request = bridge_pb2.GetWidgetChildRequest(
            widget_id=self.id, child_index=child_index, mask=self.mask
        )
        response = stub.GetWidgetChild(
            request, metadata=DIRECT_METADATA if self._use_direct_execution() else None
        )
        return self._convert_widget_response(response.widget)

    def get_children(self) -> list[dict[str, typing.Any]]:
        stub = Widget._get_stub()
        request = bridge_pb2.GetWidgetRequest(widget_id=self.id, mask=self.mask)
        response = stub.GetWidgetChildren(
            request, metadata=DIRECT_METADATA if self._use_direct_execution() else None
        )
        return [self._convert_widget_response(widget) for widget in response.widget_array]

    def get_children_masked(self, childmask: list[int]) -> list[dict[str, typing.Any]]:
        stub = Widget._get_stub()
        request = bridge_pb2.GetWidgetChildrenMaskedRequest(
            widget_id=self.id, child_mask=childmask, mask=self.mask
        )
        response = stub.GetWidgetChildrenMasked(
            request, metadata=DIRECT_METADATA if self._use_direct_execution() else None
        )
        return [self._convert_widget_response(widget) for widget in response.widget_array]

    @staticmethod
    def get_batch(widgets: list[Widget]) -> list[dict[str, typing.Any]]:
        if not widgets:
            return []
        stub = Widget._get_stub()
        ids = [w.id for w in widgets]
        masks = [w.mask for w in widgets]
        use_direct = all(w._use_direct_execution() for w in widgets)
        request = bridge_pb2.GetWidgetBatchedRequest(widget_ids=ids, mask=masks)
        response = stub.GetWidgetPropertiesBatch(
            request, metadata=DIRECT_METADATA if use_direct else None
        )
        return [Widget._convert_widget_response(widget) for widget in response.widget_array]

    @staticmethod
    def get_batch_children(widgets: list[Widget]) -> list[dict[str, typing.Any]]:
        if not widgets:
            return []
        stub = Widget._get_stub()
        ids = [w.id for w in widgets]
        masks = [w.mask for w in widgets]
        use_direct = all(w._use_direct_execution() for w in widgets)
        request = bridge_pb2.GetWidgetBatchedRequest(widget_ids=ids, mask=masks)
        response = stub.GetWidgetChildrenBatch(
            request, metadata=DIRECT_METADATA if use_direct else None
        )
        return [Widget._convert_widget_response(widget) for widget in response.widget_array]


class Buttons:
    """Fixed set of named UI buttons with cached bounds.

    Fetches all button bounds in a single batch gRPC call on first
    interaction. Subsequent interactions reuse cached bounds (zero
    Java calls) unless ``can_move=True``, which forces a fresh fetch
    each time.
    """

    def __init__(
        self,
        group: int,
        widget_ids: list[int],
        names: list[str],
        can_move: bool = False,
        menu_text: str | None = None,
    ):
        self.group = group
        self.can_move = can_move
        self.menu_text = menu_text
        self.names = names
        self.buttons: list[Widget] = []
        for id in widget_ids:
            self.buttons.append(Widget(id).enable(WidgetFields.get_bounds))
        self.boxes: list[Box | None] = []
        self._is_ready = False

    def get_names(self) -> list[str]:
        return self.names

    def _set_boxes(self) -> None:
        from escape.geometry import Box

        results = Widget.get_batch(self.buttons)
        self.boxes = []
        for r in results:
            b = r.get("bounds", {"x": 0, "y": 0, "width": 0, "height": 0})
            if b.get("width", 0) > 0 and b.get("height", 0) > 0:
                self.boxes.append(Box(b["x"], b["y"], b["width"], b["height"]))
            else:
                self.boxes.append(None)
        self._is_ready = all(box is not None for box in self.boxes)

    def interact(self, button_name: str = "", menu_option: str = "") -> bool:
        """Click a button by name.

        Finds the first button whose name contains ``button_name``
        (case-insensitive), moves the mouse to a random point within
        its bounds, and clicks the resolved menu option.

        Target text priority: ``menu_option`` > ``menu_text`` > ``button_name``.
        Fetches bounds on first call; re-fetches each call if ``can_move``.
        """
        if not self._is_ready or self.can_move:
            self._set_boxes()

        for i, name in enumerate(self.names):
            if button_name.lower() in name.lower():
                if i >= len(self.boxes):
                    continue
                box = self.boxes[i]
                if box is None:
                    continue
                target = menu_option or self.menu_text or button_name
                return box.interact(option=target)
        return False


class WidgetPanel:
    """Dynamic content panel with text search and scroll support.

    Used for UI panels whose children change at runtime (spell lists,
    prayer setup, grouping dropdowns, etc.). Widgets are matched by
    text content or action strings, and the panel will auto-scroll to
    bring off-screen matches into view.

    Args:
        group: Interface group ID used to check whether the panel is open.
        button_ids: Widget IDs whose children (or the widgets themselves)
            represent the selectable items.
        get_children: If True, fetch dynamic children of each widget;
            if False, treat the widgets themselves as the items.
        wrong_text: Hex color code for grayed-out/invalid options to
            exclude from matching (e.g. ``"5f5f5d"``).
        menu_text: Override for the right-click menu option text.
        scrollbox: Widget ID of the scroll container, if scrollable.
        max_scroll: Maximum scroll attempts before giving up.
        use_actions: Match against the widget's ``actions`` array
            instead of its ``text`` field.

    """

    def __init__(
        self,
        group: int,
        button_ids: list[int],
        get_children: bool = True,
        wrong_text: str = "5f5f5d",
        menu_text: str | None = None,
        scrollbox: int | None = None,
        max_scroll: int = 10,
        use_actions: bool = False,
    ):
        from escape._services import Services

        s = Services.get()
        self.group = group
        self.get_children = get_children
        self.wrong_text = wrong_text
        self.menu_text = menu_text
        self.scrollbox = scrollbox
        self.max_scroll = max_scroll
        self.use_actions = use_actions
        self._mouse = s.mouse
        self._cache = s.cache
        self.buttons: list[Widget] = []
        for id in button_ids:
            w = Widget(id).enable(WidgetFields.get_bounds)
            w.enable(WidgetFields.get_actions if use_actions else WidgetFields.get_text)
            self.buttons.append(w)

    def get_widget_info(self) -> list:
        if self.get_children:
            return Widget.get_batch_children(self.buttons)
        return Widget.get_batch(self.buttons)

    def is_open(self) -> bool:
        return self.group in self._cache.active_interfaces

    def is_right_option(self, w: dict, text: str = "") -> bool:
        """Check whether a widget dict matches the search text.

        When ``use_actions`` is set, matches against the actions array;
        otherwise matches against the text field and excludes entries
        containing the ``wrong_text`` color code.
        """
        text_lower = text.lower()
        if self.use_actions:
            actions = w.get("actions", []) or []
            return any(text_lower in a.lower() for a in actions if a) if text else any(actions)
        t = w.get("text", "")
        return (text_lower in t.lower() if text else bool(t)) and self.wrong_text not in t

    def _get_scrollbox(self) -> Box | None:
        from escape.geometry import Box

        if not self.scrollbox:
            return None
        widget_info = Widget(self.scrollbox).enable(WidgetFields.get_bounds).get()
        if not widget_info:
            return None
        b = widget_info.get("bounds", {"x": 0, "y": 0, "width": 0, "height": 0})
        if b.get("width", 0) > 0:
            return Box(b["x"], b["y"], b["width"], b["height"])
        return None

    def _scroll(self, sb: Box, up: bool = False) -> None:
        sb.hover()
        self._mouse.scroll(up=up, count=1)
        time.sleep(0.1)

    def _find_widget(self, text: str) -> dict | None:
        info = self.get_widget_info()
        for w in info:
            if self.is_right_option(w, text):
                return w
        return None

    def _make_visible(self, text: str, sb: Box | None) -> Box | None:
        from escape.geometry import Box

        w = self._find_widget(text)
        if not w:
            return None
        for _ in range(self.max_scroll + 1):
            b = w.get("bounds", {"x": 0, "y": 0, "width": 0, "height": 0})
            if b.get("width", 0) > 0:
                box = Box(b["x"], b["y"], b["width"], b["height"])
                if not sb or sb.contains(box):
                    return box
                self._scroll(sb, up=box.y < sb.y)
            w = self._find_widget(text)
            if not w:
                return None
        return None

    def interact(self, option_text: str = "") -> bool:
        if not self.is_open():
            return False
        box = self._make_visible(option_text, self._get_scrollbox())
        if not box:
            return False
        return box.interact(option=self.menu_text or option_text)
