from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from escape._math import _chebyshev

if TYPE_CHECKING:
    from escape.geometry import Quad
    from escape.navigation.navigator import Navigator
    from escape.navigation.open_bank import OpenBank
    from escape.navigation.registry import SolverRegistry
    from escape.pathfinder import Path, Pathfinder, PathfinderConfig
    from escape.point import Point
    from escape.projection import TileGrid
    from escape.scene import Scene

LOCAL_UNITS_PER_TILE = 128


class Walker:
    def __init__(
        self,
        scene: Scene,
        pathfinder: Pathfinder,
        registry: SolverRegistry | None = None,
    ):
        from escape._services import Services

        s = Services.get()
        self._cache = s.cache
        self._scene = scene
        self._pathfinder = pathfinder
        self._registry: SolverRegistry | None = registry
        self._last_walk_tile: tuple[int, int] | None = None

    def navigate(
        self,
        dest: Point,
        config: PathfinderConfig | None = None,
        arrival_threshold: int = 2,
    ) -> Navigator:
        """Create a Navigator for multi-step navigation through transports."""
        from escape.navigation.navigator import Navigator

        if self._registry is None:
            raise RuntimeError("Walker has no solver registry — pass one to Walker() or use Client")
        return Navigator(dest, self, self._pathfinder, self._registry, config, arrival_threshold)

    def open_bank(self, config: PathfinderConfig | None = None) -> OpenBank:
        """Create an OpenBank state machine for navigating to and opening the nearest bank."""
        from escape.navigation.open_bank import OpenBank

        if self._registry is None:
            raise RuntimeError("Walker has no solver registry — pass one to Walker() or use Client")
        return OpenBank(self, self._pathfinder, self._registry, config)

    def _distance_to_target(self) -> int | None:
        player_pos = self._cache.position
        target_pos = self._cache.target_position

        if player_pos is None or target_pos is None:
            return None

        # (0, 0) means no destination (null LocalPoint in Java)
        if target_pos[0] == 0 and target_pos[1] == 0:
            return None

        # target_position is in local units (128/tile), position is in scene tiles
        target_tile_x = target_pos[0] >> 7
        target_tile_y = target_pos[1] >> 7
        return _chebyshev(target_tile_x, target_tile_y, player_pos[0], player_pos[1])

    def has_target(self) -> bool:
        return self._cache.target_position is not None

    def is_near_target(self, threshold: int = 2) -> bool:
        dist = self._distance_to_target()
        if dist is None:
            return True
        return dist <= threshold

    def should_click_new_tile(self, threshold: int = 2) -> bool:
        return self.is_near_target(threshold=threshold)

    def _find_first_transport_index(self, path: Path) -> int:
        if not path.transports:
            return path.length()

        first_idx = path.length()
        for transport in path.transports:
            matches = np.where(path._packed == transport.origin.packed)[0]
            if len(matches) > 0:
                idx = int(matches[0])
                if idx < first_idx:
                    first_idx = idx

        return first_idx

    def _select_walk_tile(
        self,
        path: Path,
        visible_indices: np.ndarray,
        player_x: int,
        player_y: int,
        max_index: int,
        grid: TileGrid | None = None,
    ) -> int | None:
        valid_indices = visible_indices[visible_indices < max_index]

        if len(valid_indices) == 0:
            return None

        world_x = path.world_x[valid_indices]
        world_y = path.world_y[valid_indices]
        dist = np.maximum(np.abs(world_x - player_x), np.abs(world_y - player_y))
        within_range = dist <= 19
        valid_indices = valid_indices[within_range]

        if len(valid_indices) == 0:
            return None

        if grid is None:
            grid = self._scene._get_tile_grid()
        if grid is None:
            return None

        clickable_indices = []
        for idx in valid_indices:
            quad = self._scene.get_tile_quad(int(path.world_x[idx]), int(path.world_y[idx]))
            if quad is not None:
                all_inside = all(
                    grid.view_min_x <= p.x <= grid.view_max_x
                    and grid.view_min_y <= p.y <= grid.view_max_y
                    for p in quad.vertices
                )
                if all_inside:
                    clickable_indices.append(int(idx))

        if len(clickable_indices) == 0:
            return None

        clickable_indices = np.array(clickable_indices)

        world_x = path.world_x[clickable_indices]
        world_y = path.world_y[clickable_indices]

        dist = np.maximum(np.abs(world_x - player_x), np.abs(world_y - player_y))

        far_enough = dist >= 3
        if not far_enough.any():
            best_local = int(np.argmax(dist))
            return int(clickable_indices[best_local])

        far_mask = np.array(far_enough)
        far_indices = clickable_indices[far_mask]
        return int(far_indices[-1])

    def click_tile(self, world_x: int, world_y: int) -> bool:
        quad = self._scene.get_tile_quad(world_x, world_y)
        if quad is None:
            return False
        return self._click_walk_quad(quad)

    def walk_path(self, path: Path, stop_before: int = -1, margin: int = 50) -> bool:
        """Walk along a pre-computed path, stopping before the given tile index.

        Args:
            path: Pre-computed path to walk.
            stop_before: Tile index to stop before (e.g. transport origin).
                         -1 means walk to end.
            margin: Pixel margin for viewport visibility check.

        Returns:
            True if a tile was clicked or no click needed, False on failure.

        """
        from escape._logger import logger

        player_x, player_y, _ = self._cache.world_position

        max_index = stop_before if stop_before >= 0 else path.length()

        grid = self._scene._get_tile_grid()
        if grid is None:
            logger.debug("walk: no tile grid")
            return False

        visible_indices = grid.get_world_visible_indices(path.world_x, path.world_y, margin=margin)
        if len(visible_indices) == 0:
            logger.debug("walk: no visible tiles")
            return False

        target_idx = self._select_walk_tile(
            path, visible_indices, player_x, player_y, max_index, grid=grid
        )
        if target_idx is None:
            logger.debug(
                "walk: no suitable tile (visible={} max_idx={})", len(visible_indices), max_index
            )
            return False

        wx, wy = int(path.world_x[target_idx]), int(path.world_y[target_idx])
        quad = self._scene.get_tile_quad(wx, wy)
        if quad is None:
            logger.debug("walk: no quad for ({}, {})", wx, wy)
            return False

        logger.debug("walk → click ({}, {}) idx={}/{}", wx, wy, target_idx, max_index)
        self._last_walk_tile = (wx, wy)
        return self._click_walk_quad(quad)

    def walk_to(
        self,
        dest_x: int,
        dest_y: int,
        dest_plane: int = 0,
        margin: int = 50,
        near_target_threshold: int = 2,
        config: PathfinderConfig | None = None,
    ) -> bool:
        player_x, player_y, player_plane = self._cache.world_position

        if player_x == dest_x and player_y == dest_y and player_plane == dest_plane:
            return True

        if not self.should_click_new_tile(threshold=near_target_threshold):
            return True

        path = self._pathfinder.find_path((dest_x, dest_y, dest_plane), config=config)
        if not path.found or path.is_empty():
            return False

        obstacle_idx = self._find_first_transport_index(path)
        return self.walk_path(path, stop_before=obstacle_idx, margin=margin)

    def _click_walk_quad(self, quad: Quad) -> bool:
        return quad.interact(action="WALK")

    def is_moving(self) -> bool:
        return self.has_target()

    def distance_to_destination(self, dest_x: int, dest_y: int) -> int:
        player_x, player_y, _ = self._cache.world_position
        return _chebyshev(dest_x, dest_y, player_x, player_y)
