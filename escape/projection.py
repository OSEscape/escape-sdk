"""Projection utilities for converting local coordinates to screen coordinates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from escape.point import ScreenPoint

if TYPE_CHECKING:
    from escape.geometry import Quad


@dataclass
class EntityTransform:
    """Entity transform with position, orientation, and ground height."""

    entity_x: int
    entity_y: int
    orientation: int
    ground_height: int


@dataclass
class EntityConfig:
    """Entity bounding box configuration in local coordinates."""

    bounds_x: int
    bounds_y: int
    bounds_width: int
    bounds_height: int

    @property
    def center_x(self) -> int:
        """Center X in local coordinates."""
        return (self.bounds_x + self.bounds_width // 2) * 128

    @property
    def center_y(self) -> int:
        """Center Y in local coordinates."""
        return (self.bounds_y + self.bounds_height // 2) * 128


class TileGrid:
    """Cached projection of all tile corners in the scene."""

    __slots__ = (
        "_scene_xs",
        "_scene_ys",
        "_tile_on_screen",
        "_tile_valid",
        "base_x",
        "base_y",
        "corner_valid",
        "corner_x",
        "corner_y",
        "plane",
        "size_x",
        "size_y",
        "view_max_x",
        "view_max_y",
        "view_min_x",
        "view_min_y",
    )

    def __init__(
        self,
        corner_x: np.ndarray,
        corner_y: np.ndarray,
        corner_valid: np.ndarray,
        size_x: int,
        size_y: int,
        base_x: int,
        base_y: int,
        plane: int,
        view_min_x: int,
        view_max_x: int,
        view_min_y: int,
        view_max_y: int,
    ):
        self.corner_x = corner_x
        self.corner_y = corner_y
        self.corner_valid = corner_valid
        self.size_x = size_x
        self.size_y = size_y
        self.base_x = base_x
        self.base_y = base_y
        self.plane = plane
        self.view_min_x = view_min_x
        self.view_max_x = view_max_x
        self.view_min_y = view_min_y
        self.view_max_y = view_max_y

        tile_count = size_x * size_y
        self._scene_xs = (np.arange(tile_count, dtype=np.int32) // size_y).astype(np.int16)
        self._scene_ys = (np.arange(tile_count, dtype=np.int32) % size_y).astype(np.int16)

        self._tile_valid: np.ndarray | None = None
        self._tile_on_screen: np.ndarray | None = None

    def _corner_idx(self, x: int, y: int) -> int:
        return x * (self.size_y + 1) + y

    def _tile_idx(self, x: int, y: int) -> int:
        return x * self.size_y + y

    @property
    def tile_valid(self) -> np.ndarray:
        """Boolean mask of tiles with all four corners projected."""
        if self._tile_valid is None:
            sy1 = self.size_y + 1
            tile_idxs = np.arange(self.size_x * self.size_y, dtype=np.int32)
            tx = tile_idxs // self.size_y
            ty = tile_idxs % self.size_y
            nw = tx * sy1 + ty
            ne = (tx + 1) * sy1 + ty
            se = (tx + 1) * sy1 + (ty + 1)
            sw = tx * sy1 + (ty + 1)
            self._tile_valid = (
                self.corner_valid[nw]
                & self.corner_valid[ne]
                & self.corner_valid[se]
                & self.corner_valid[sw]
            )
        return self._tile_valid

    @property
    def tile_on_screen(self) -> np.ndarray:
        """Boolean mask of tiles visible within the viewport."""
        if self._tile_on_screen is None:
            center_x, center_y = self.get_tile_centers()
            self._tile_on_screen = (
                self.tile_valid
                & (center_x >= self.view_min_x)
                & (center_x < self.view_max_x)
                & (center_y >= self.view_min_y)
                & (center_y < self.view_max_y)
            )
        return self._tile_on_screen

    def get_tile_centers(self) -> tuple[np.ndarray, np.ndarray]:
        """Return screen-space center coordinates for all tiles."""
        sy1 = self.size_y + 1
        tile_idxs = np.arange(self.size_x * self.size_y, dtype=np.int32)
        tx = tile_idxs // self.size_y
        ty = tile_idxs % self.size_y
        nw = tx * sy1 + ty
        ne = (tx + 1) * sy1 + ty
        se = (tx + 1) * sy1 + (ty + 1)
        sw = tx * sy1 + (ty + 1)
        center_x = (
            self.corner_x[nw] + self.corner_x[ne] + self.corner_x[se] + self.corner_x[sw]
        ) >> 2
        center_y = (
            self.corner_y[nw] + self.corner_y[ne] + self.corner_y[se] + self.corner_y[sw]
        ) >> 2
        return center_x, center_y

    def get_tile_corners(self, tile_idx: int) -> tuple[int, int, int, int, int, int, int, int]:
        """Return the four screen-space corner coordinates for a tile."""
        tx = tile_idx // self.size_y
        ty = tile_idx % self.size_y
        sy1 = self.size_y + 1
        nw = tx * sy1 + ty
        ne = (tx + 1) * sy1 + ty
        se = (tx + 1) * sy1 + (ty + 1)
        sw = tx * sy1 + (ty + 1)
        return (
            int(self.corner_x[nw]),
            int(self.corner_y[nw]),
            int(self.corner_x[ne]),
            int(self.corner_y[ne]),
            int(self.corner_x[se]),
            int(self.corner_y[se]),
            int(self.corner_x[sw]),
            int(self.corner_y[sw]),
        )

    def get_tile_quad(self, tile_idx: int) -> Quad:
        """Return a Quad geometry for the given tile index."""
        from escape.geometry import Quad

        nw_x, nw_y, ne_x, ne_y, se_x, se_y, sw_x, sw_y = self.get_tile_corners(tile_idx)
        return Quad.from_coords([(nw_x, nw_y), (ne_x, ne_y), (se_x, se_y), (sw_x, sw_y)])

    def get_world_visible_indices(
        self,
        world_x: np.ndarray,
        world_y: np.ndarray,
        margin: int = 0,
    ) -> np.ndarray:
        """Return indices of world coordinates that are visible on screen."""
        scene_x = world_x - self.base_x
        scene_y = world_y - self.base_y

        in_scene = (
            (scene_x >= 0) & (scene_x < self.size_x) & (scene_y >= 0) & (scene_y < self.size_y)
        )

        if not in_scene.any():
            return np.array([], dtype=np.intp)

        clipped_x = scene_x.clip(0, self.size_x - 1)
        clipped_y = scene_y.clip(0, self.size_y - 1)
        tile_idx = clipped_x * self.size_y + clipped_y

        center_x, center_y = self.get_tile_centers()
        sx = center_x[tile_idx]
        sy = center_y[tile_idx]

        tile_valid = self.tile_valid[tile_idx]

        if margin == 0:
            on_screen = (
                (sx >= self.view_min_x)
                & (sx < self.view_max_x)
                & (sy >= self.view_min_y)
                & (sy < self.view_max_y)
            )
        else:
            on_screen = (
                (sx >= self.view_min_x - margin)
                & (sx < self.view_max_x + margin)
                & (sy >= self.view_min_y - margin)
                & (sy < self.view_max_y + margin)
            )

        visible = in_scene & tile_valid & on_screen
        return np.where(visible)[0]

    def get_visible_indices(self, mask: np.ndarray | None = None, margin: int = 0) -> np.ndarray:
        """Return flat indices of tiles visible on screen."""
        if margin == 0:
            visible = self.tile_on_screen
        else:
            center_x, center_y = self.get_tile_centers()
            visible = (
                self.tile_valid
                & (center_x >= self.view_min_x - margin)
                & (center_x < self.view_max_x + margin)
                & (center_y >= self.view_min_y - margin)
                & (center_y < self.view_max_y + margin)
            )

        if mask is not None:
            visible = visible & mask

        return np.where(visible)[0]


class Projection:
    """Fast projection from local coordinates to canvas coordinates."""

    LOCAL_COORD_BITS = 7
    LOCAL_TILE_SIZE = 128

    VIEWPORT_WIDTH = 512
    VIEWPORT_HEIGHT = 334
    VIEWPORT_X_OFFSET = 4
    VIEWPORT_Y_OFFSET = 4

    def __init__(self):
        from escape._services import Services

        self._cache = Services.get().cache
        unit = np.pi / 1024
        angles = np.arange(2048) * unit
        self._sin_table = np.sin(angles).astype(np.float32)
        self._cos_table = np.cos(angles).astype(np.float32)

        self.tile_heights: np.ndarray | None = None
        self.bridge_flags: np.ndarray | None = None
        self.base_x: int = 0
        self.base_y: int = 0
        self.size_x: int = 104
        self.size_y: int = 104
        self.entity_config: EntityConfig | None = None

        self._cam_x: float = 0
        self._cam_y: float = 0
        self._cam_z: float = 0
        self._scale: int = 512
        self._pitch_sin: float = 0
        self._pitch_cos: float = 1
        self._yaw_sin: float = 0
        self._yaw_cos: float = 1

        self._entity_x: int = 0
        self._entity_y: int = 0
        self._orient_sin: float = 0
        self._orient_cos: float = 1
        self._ground_height: int = 0
        self._center_x: int = 0
        self._center_y: int = 0

        self._tile_grid: TileGrid | None = None
        self._scene_version: int = 0
        self._camera_version: int = 0

    @property
    def tiles(self) -> TileGrid | None:
        """Cached tile grid projection, recomputed when camera or scene changes."""
        cache = self._cache
        camera_ver = cache.camera_version
        scene_ver = cache.world_view_version

        if (
            self._tile_grid is not None
            and camera_ver == self._camera_version
            and scene_ver == self._scene_version
        ):
            return self._tile_grid

        if not self._refresh_camera():
            return None

        if scene_ver != self._scene_version:
            if not self._sync_scene_from_cache():
                return None

        self._camera_version = camera_ver
        self._compute_tile_grid()
        return self._tile_grid

    def _refresh_camera(self) -> bool:
        camera = self._cache.camera
        if not camera:
            return False

        self._cam_x, self._cam_y, self._cam_z = camera.camera_x, camera.camera_y, camera.camera_z
        pitch, yaw, self._scale = camera.pitch, camera.yaw, camera.scale
        self._pitch_sin = np.sin(pitch)
        self._pitch_cos = np.cos(pitch)
        self._yaw_sin = np.sin(yaw)
        self._yaw_cos = np.cos(yaw)

        entity = self._cache.world_entity
        if entity:
            self._entity_x, self._entity_y = entity.entity_x, entity.entity_y
            self._orient_sin = float(self._sin_table[entity.orientation])
            self._orient_cos = float(self._cos_table[entity.orientation])
            self._ground_height = entity.ground_height_offset
        else:
            self._entity_x = self._entity_y = self._ground_height = 0
            self._orient_sin, self._orient_cos = 0.0, 1.0

        return True

    def _compute_tile_grid(self):
        plane = self._cache.plane or 0

        cx = np.arange(self.size_x + 1, dtype=np.int32)
        cy = np.arange(self.size_y + 1, dtype=np.int32)
        grid_x, grid_y = np.meshgrid(cx, cy, indexing="ij")

        local_x = (grid_x << 7).ravel().astype(np.float32)
        local_y = (grid_y << 7).ravel().astype(np.float32)

        screen_x, screen_y, valid = self._project_batch(local_x, local_y, plane)

        self._tile_grid = TileGrid(
            corner_x=screen_x.astype(np.int32),
            corner_y=screen_y.astype(np.int32),
            corner_valid=valid,
            size_x=self.size_x,
            size_y=self.size_y,
            base_x=self.base_x,
            base_y=self.base_y,
            plane=plane,
            view_min_x=self.VIEWPORT_X_OFFSET,
            view_max_x=self.VIEWPORT_X_OFFSET + self.VIEWPORT_WIDTH,
            view_min_y=self.VIEWPORT_Y_OFFSET,
            view_max_y=self.VIEWPORT_Y_OFFSET + self.VIEWPORT_HEIGHT,
        )

    def _project_batch(
        self, local_x: np.ndarray, local_y: np.ndarray, plane: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self.bridge_flags is None or self.tile_heights is None:
            raise RuntimeError("Projection scene data not initialized")

        # Clip to height array bounds (vertex-based, size_x+1 x size_y+1)
        scene_x = (local_x.astype(np.int32) >> 7).clip(0, self.tile_heights.shape[1] - 1)
        scene_y = (local_y.astype(np.int32) >> 7).clip(0, self.tile_heights.shape[2] - 1)
        bf_x = scene_x.clip(0, self.bridge_flags.shape[0] - 1)
        bf_y = scene_y.clip(0, self.bridge_flags.shape[1] - 1)
        tile_plane = np.where((plane < 3) & self.bridge_flags[bf_x, bf_y], plane + 1, plane)
        z = self.tile_heights[tile_plane, scene_x, scene_y].astype(np.float32) + self._ground_height

        if self.entity_config is None:
            world_x, world_y = local_x, local_y
        else:
            cx = local_x - self._center_x
            cy = local_y - self._center_y
            world_x = self._entity_x + cy * self._orient_sin + cx * self._orient_cos
            world_y = self._entity_y + cy * self._orient_cos - cx * self._orient_sin

        dx = world_x - self._cam_x
        dy = world_y - self._cam_y
        dz = z - self._cam_z

        x1 = dx * self._yaw_cos + dy * self._yaw_sin
        y1 = dy * self._yaw_cos - dx * self._yaw_sin
        y2 = dz * self._pitch_cos - y1 * self._pitch_sin
        depth = y1 * self._pitch_cos + dz * self._pitch_sin

        valid = depth >= 50
        safe_depth = np.where(valid, depth, 1.0)
        screen_x = (self.VIEWPORT_WIDTH / 2 + x1 * self._scale / safe_depth).astype(np.int32)
        screen_y = (self.VIEWPORT_HEIGHT / 2 + y2 * self._scale / safe_depth).astype(np.int32)
        screen_x += self.VIEWPORT_X_OFFSET
        screen_y += self.VIEWPORT_Y_OFFSET

        return screen_x, screen_y, valid

    def _sync_scene_from_cache(self) -> bool:
        """Pull scene geometry from the cache's world view proto."""
        wv = self._cache.world_view
        if wv is None or not wv.tile_heights or not wv.size_x or not wv.size_y:
            return False

        num_planes = len(wv.tile_heights) // (wv.size_x * wv.size_y)
        if num_planes == 0:
            return False

        tile_heights = np.array(wv.tile_heights, dtype=np.int32).reshape(
            num_planes, wv.size_x, wv.size_y
        )
        if wv.bridge_flags:
            bf_len = len(wv.bridge_flags)
            bf_side = int(bf_len**0.5)
            bridge_flags = np.array(wv.bridge_flags, dtype=bool).reshape(bf_side, bf_side)
        else:
            bridge_flags = np.zeros((wv.size_x, wv.size_y), dtype=bool)

        # size_x/size_y in proto are vertex counts (105); tile count is one less (104)
        self.set_scene(
            tile_heights, bridge_flags, wv.base_x, wv.base_y, wv.size_x - 1, wv.size_y - 1
        )
        self._scene_version = self._cache.world_view_version
        return True

    def set_scene(
        self,
        tile_heights: np.ndarray,
        bridge_flags: np.ndarray,
        base_x: int,
        base_y: int,
        size_x: int,
        size_y: int,
    ):
        """Set the scene geometry data for projection."""
        self.tile_heights = tile_heights.astype(np.int32)
        self.bridge_flags = bridge_flags.astype(np.bool_)
        self.base_x = base_x
        self.base_y = base_y
        self.size_x = size_x
        self.size_y = size_y

    def set_entity_config(self, config: EntityConfig | None):
        """Set the entity bounding box configuration for projection."""
        self.entity_config = config
        if config:
            self._center_x = config.center_x
            self._center_y = config.center_y
        else:
            self._center_x = self._center_y = 0

    def world_tile_to_canvas(self, world_x: int, world_y: int, plane: int) -> ScreenPoint | None:
        """Convert a world tile coordinate to a canvas screen point."""
        grid = self.tiles
        if grid is None or grid.plane != plane:
            return None

        scene_x = world_x - self.base_x
        scene_y = world_y - self.base_y
        if not (0 <= scene_x < self.size_x and 0 <= scene_y < self.size_y):
            return None

        tile_idx = scene_x * self.size_y + scene_y
        if not grid.tile_valid[tile_idx]:
            return None

        center_x, center_y = grid.get_tile_centers()
        return ScreenPoint(int(center_x[tile_idx]), int(center_y[tile_idx]))
