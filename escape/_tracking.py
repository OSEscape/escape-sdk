from typing import TYPE_CHECKING

from google.protobuf.empty_pb2 import Empty

from escape._proto.bridge.v1 import bridge_pb2

if TYPE_CHECKING:
    from escape._cache.processed_cache import ProcessedCache
    from escape.geometry import Polygon
    from escape.input import Mouse
    from escape.menu import Menu


class ClickboxTracker:
    def __init__(self, stub, cache: ProcessedCache, menu: Menu, mouse: Mouse) -> None:
        self._stub = stub
        self._cache = cache
        self._menu = menu
        self._mouse = mouse

    def track_ground_item(self, packed_location: int, item_id: int, debug: bool = False) -> None:
        request = bridge_pb2.StartClickboxTrackingRequest(
            ground_item=bridge_pb2.GroundItemTarget(
                packed_location=packed_location, item_id=item_id
            ),
            debug=debug,
        )
        self._stub.StartClickboxTracking(request)

    def track_npc(self, npc_index: int, debug: bool = False) -> None:
        request = bridge_pb2.StartClickboxTrackingRequest(
            npc=bridge_pb2.NpcTarget(npc_index=npc_index), debug=debug
        )
        self._stub.StartClickboxTracking(request)

    def track_object(self, packed_location: int, object_id: int, debug: bool = False) -> None:
        request = bridge_pb2.StartClickboxTrackingRequest(
            object=bridge_pb2.ObjectTarget(packed_location=packed_location, object_id=object_id),
            debug=debug,
        )
        self._stub.StartClickboxTracking(request)

    def track_tile(self, packed_location: int, debug: bool = False) -> None:
        request = bridge_pb2.StartClickboxTrackingRequest(
            tile=bridge_pb2.TileTarget(packed_location=packed_location), debug=debug
        )
        self._stub.StartClickboxTracking(request)

    def stop(self) -> None:
        self._stub.StopClickboxTracking(Empty())

    @property
    def vertices(self) -> list[list[int]] | None:
        update = self._cache.clickbox_update
        if update is None or not update.target_exists:
            return None
        from escape.projection import Projection

        x_min = Projection.VIEWPORT_X_OFFSET
        x_max = Projection.VIEWPORT_X_OFFSET + Projection.VIEWPORT_WIDTH
        y_min = Projection.VIEWPORT_Y_OFFSET
        y_max = Projection.VIEWPORT_Y_OFFSET + Projection.VIEWPORT_HEIGHT
        flat = list(update.vertices)
        return [
            [max(x_min, min(flat[i], x_max)), max(y_min, min(flat[i + 1], y_max))]
            for i in range(0, len(flat), 2)
        ]

    @property
    def target_exists(self) -> bool:
        update = self._cache.clickbox_update
        return update is not None and update.target_exists

    def get_polygon(self) -> Polygon | None:
        vertices = self.vertices
        if vertices is None:
            return None
        from escape.geometry import Polygon
        from escape.point import ScreenPoint

        return Polygon(vertices=[ScreenPoint(x, y) for x, y in vertices])

    def click(
        self,
        button: str = "left",
        menu_action: str | None = None,
        option: str | None = None,
    ) -> bool:
        if not self.target_exists:
            return False

        self.hover()

        if menu_action:
            if not self._menu.wait_has_menu_action(menu_action):
                from escape._logger import logger

                logger.warning("Menu action '{}' not found after hovering target", menu_action)
                return False
            return self._menu.click_option_action(menu_action)
        elif option:
            if not self._menu.wait_has_option(option):
                from escape._logger import logger

                logger.warning("Menu option '{}' not found after hovering target", option)
                return False
            return self._menu.click_option(option)
        else:
            if button == "left":
                self._mouse.left_click()
            elif button == "right":
                self._mouse.right_click()
            else:
                return False
            return True

    def hover(self) -> bool:
        if not self.target_exists:
            return False

        def get_current_polygon() -> Polygon:
            poly = self.get_polygon()
            if poly is None:
                raise RuntimeError("Target no longer exists")
            return poly

        self._mouse.hover_polygon(get_current_polygon)
        return True

    def right_click(self) -> bool:
        return self.click(button="right")
