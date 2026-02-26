from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from escape._logger import logger
from escape.bt.actions import Status
from escape.pathfinding.pathfinder.osrs_pathfinder import (
    _can_step_osrs,
    bfs_to_object,
    bfs_to_tile,
)
from escape.point import Point

if TYPE_CHECKING:
    from escape._cache.processed_cache import ProcessedCache
    from escape.pathfinder import Pathfinder
    from escape.walker import Walker

# Direction (dx, dy) → osrs_pathfinder direction index
# Indices: W=0, E=1, S=2, N=3, SW=4, SE=5, NW=6, NE=7
_DIR_MAP: dict[tuple[int, int], int] = {
    (-1, 0): 0,
    (1, 0): 1,
    (0, -1): 2,
    (0, 1): 3,
    (-1, -1): 4,
    (1, -1): 5,
    (-1, 1): 6,
    (1, 1): 7,
}


class Walk:
    """Walk-to-point state machine.

    Uses static BFS to find a path, validates against live collision data,
    then clicks the best visible tile. Framework-agnostic.
    """

    def __init__(
        self,
        target: Point,
        walker: Walker,
        pathfinder: Pathfinder,
        arrival_threshold: int = 2,
    ) -> None:
        self._target = target
        self._walker = walker
        self._pathfinder = pathfinder
        self._arrival_threshold = arrival_threshold
        self._last_static_tiles: list[tuple[int, int, int]] = []

    @property
    def _cache(self) -> ProcessedCache:
        from escape._services import Services

        return Services.get().cache

    @property
    def last_static_tiles(self) -> list[tuple[int, int, int]]:
        return self._last_static_tiles

    def reset(self, target: Point | None = None) -> None:
        if target is not None:
            self._target = target
        self._last_static_tiles = []

    def tick(self) -> Status:
        pos = self._cache.world_position
        if pos is None:
            return Status.RUNNING
        player_wx, player_wy, plane = pos

        # Try live BFS approach when target is in the loaded scene
        live_tiles = self._try_live_approach(player_wx, player_wy, plane)
        if live_tiles is not None:
            self._last_static_tiles = live_tiles
            return self._pick_and_click(live_tiles)

        # Fall through to static path → validate → truncate
        static_tiles = self._pathfinder.find_static_path(
            Point(player_wx, player_wy, plane),
            self._target,
        )
        if not static_tiles:
            logger.debug("walk: static BFS found no path")
            return Status.FAILURE

        self._last_static_tiles = static_tiles

        # Validate against live collision
        validated_tiles = self._validate_path(static_tiles, plane)

        if len(validated_tiles) <= 1:
            # Can't even take first step — blocked
            return Status.FAILURE

        # Walk the validated portion
        return self._pick_and_click(validated_tiles)

    def _validate_path(
        self,
        tiles: list[tuple[int, int, int]],
        plane: int,
    ) -> list[tuple[int, int, int]]:
        """Validate static path steps against live collision flags.

        Returns the prefix of tiles that are walkable on live collision data.
        """
        collision = self._cache.collision_flags
        if collision is None:
            return tiles

        wv = self._cache.world_view
        if wv is None:
            return tiles

        flags = collision[plane].T  # [y, x] for osrs_pathfinder
        h, w = flags.shape
        base_x = wv.base_x
        base_y = wv.base_y

        validated = [tiles[0]]
        for i in range(len(tiles) - 1):
            ax, ay, _ = tiles[i]
            bx, by, _ = tiles[i + 1]

            # Convert to scene coords
            sx = ax - base_x
            sy = ay - base_y
            nx = bx - base_x
            ny = by - base_y

            # Check bounds
            if not (0 <= sx < w and 0 <= sy < h and 0 <= nx < w and 0 <= ny < h):
                # Out of scene — trust static path for remaining tiles
                validated.extend(tiles[i + 1 :])
                break

            dx = nx - sx
            dy = ny - sy
            di = _DIR_MAP.get((dx, dy))
            if di is None:
                # Non-adjacent step (teleport or multi-tile jump) — trust it
                validated.append(tiles[i + 1])
                continue

            if not _can_step_osrs(flags, w, h, sx, sy, di):
                # Blocked — stop here
                logger.debug(
                    "walk: live collision blocks step {} → {} (di={})",
                    (ax, ay), (bx, by), di,
                )
                break

            validated.append(tiles[i + 1])

        return validated

    def _pick_and_click(self, world_tiles: list[tuple[int, int, int]]) -> Status:
        """Select the best tile from the validated path and click it."""
        if not self._walker.should_click_new_tile(threshold=2):
            return Status.RUNNING

        wx = np.array([t[0] for t in world_tiles], dtype=np.int32)
        wy = np.array([t[1] for t in world_tiles], dtype=np.int32)

        grid = self._walker._scene._get_tile_grid()
        if grid is None:
            return Status.RUNNING

        visible = grid.get_world_visible_indices(wx, wy, margin=50)
        if len(visible) == 0:
            logger.debug("walk: no visible tiles on local path")
            return Status.RUNNING

        pos = self._cache.world_position
        if pos is None:
            return Status.RUNNING
        player_x, player_y, _ = pos

        target_idx = self._select_tile(wx, wy, visible, player_x, player_y, grid)
        if target_idx is None:
            logger.debug("walk: no clickable tile on local path")
            return Status.RUNNING

        tile_wx, tile_wy = int(wx[target_idx]), int(wy[target_idx])
        quad = self._walker._scene.get_tile_quad(tile_wx, tile_wy)
        if quad is None:
            return Status.RUNNING

        logger.debug("walk → click ({}, {}) idx={}/{}", tile_wx, tile_wy, target_idx, len(world_tiles))
        self._walker._click_walk_quad(quad)
        return Status.RUNNING

    def _select_tile(
        self,
        wx: np.ndarray,
        wy: np.ndarray,
        visible_indices: np.ndarray,
        player_x: int,
        player_y: int,
        grid: object,
    ) -> int | None:
        """Pick the best tile to click — furthest visible, ≥3 from player, quad on screen."""
        from escape.projection import TileGrid

        assert isinstance(grid, TileGrid)

        world_x = wx[visible_indices]
        world_y = wy[visible_indices]
        dist = np.maximum(np.abs(world_x - player_x), np.abs(world_y - player_y))

        within_range = dist <= 19
        valid = visible_indices[within_range]
        if len(valid) == 0:
            return None

        clickable = []
        for idx in valid:
            quad = self._walker._scene.get_tile_quad(int(wx[idx]), int(wy[idx]))
            if quad is not None:
                all_inside = all(
                    grid.view_min_x <= p.x <= grid.view_max_x
                    and grid.view_min_y <= p.y <= grid.view_max_y
                    for p in quad.vertices
                )
                if all_inside:
                    clickable.append(int(idx))

        if not clickable:
            return None

        clickable_arr = np.array(clickable)
        c_dist = np.maximum(np.abs(wx[clickable_arr] - player_x), np.abs(wy[clickable_arr] - player_y))

        far_enough = c_dist >= 3
        if far_enough.any():
            far_indices = clickable_arr[far_enough]
            return int(far_indices[-1])
        return int(clickable_arr[np.argmax(c_dist)])

    def _try_live_approach(
        self, player_wx: int, player_wy: int, plane: int,
    ) -> list[tuple[int, int, int]] | None:
        """Try live BFS to target, falling back to bfs_to_object if blocked."""
        collision = self._cache.collision_flags
        if collision is None:
            return None
        wv = self._cache.world_view
        if wv is None:
            return None

        base_x, base_y = wv.base_x, wv.base_y
        flags = collision[plane].T  # [y, x] for osrs_pathfinder
        h, w = flags.shape

        sx = player_wx - base_x
        sy = player_wy - base_y
        gx = self._target.x - base_x
        gy = self._target.y - base_y

        # Target not in scene — skip live approach
        if not (0 <= gx < w and 0 <= gy < h):
            return None

        # Try direct live BFS
        px, py, n = bfs_to_tile(flags, sx, sy, gx, gy)
        if n > 1:
            return [(int(px[i]) + base_x, int(py[i]) + base_y, plane) for i in range(n)]

        # Target blocked — find SceneObject whose footprint contains it
        target_tile = (self._target.x, self._target.y, plane)
        for obj in self._cache.scene_objects:
            if obj.plane != plane:
                continue
            if target_tile in obj.tiles:
                obj_sx = obj.sw_x - base_x
                obj_sy = obj.sw_y - base_y
                px, py, n = bfs_to_object(
                    flags, sx, sy, obj_sx, obj_sy, obj.size_x, obj.size_y,
                )
                if n > 1:
                    logger.debug(
                        "walk: live bfs_to_object '{}' → {} tiles", obj.name, n,
                    )
                    return [(int(px[i]) + base_x, int(py[i]) + base_y, plane) for i in range(n)]
                break

        return None
