"""Camera control module using middle-mouse-drag rotation."""

from __future__ import annotations

import math
import random
import time
from typing import TYPE_CHECKING

from escape._logger import logger

if TYPE_CHECKING:
    from escape._cache.processed_cache import ProcessedCache
    from escape.input import Mouse, RuneLite

TWO_PI = 2.0 * math.pi
_EDGE = 100
_PX_PER_DEG = 2.83


class Camera:
    """Rotate the OSRS camera by dragging with the middle mouse button.

    Singleton — use ``Camera()`` to obtain the shared instance.
    """

    _instance: Camera | None = None

    def __new__(cls) -> Camera:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def __init__(self) -> None:
        pass

    def _init(self) -> None:
        from escape._services import Services

        s = Services.get()
        self._cache: ProcessedCache = s.cache
        self._mouse: Mouse = s.mouse
        self._runelite: RuneLite = s.runelite

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_angle(
        self,
        compass_angle: float | None = None,
        pitch: float | None = None,
        tolerance: float = 10.0,
        timeout: float = 3.0,
    ) -> bool:
        """Set camera orientation via middle-mouse drag."""
        if compass_angle is None and pitch is None:
            return True

        tol = math.radians(tolerance)
        target_yaw = math.radians(compass_angle) % TWO_PI if compass_angle is not None else None
        target_pitch = math.radians(max(40.0, min(90.0, pitch))) if pitch is not None else None

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            cam = self._cache.camera
            if cam is None:
                return False

            yaw_diff = self._shortest_diff(target_yaw, cam.yaw) if target_yaw is not None else 0.0
            pitch_diff = (target_pitch - cam.pitch) if target_pitch is not None else 0.0

            if abs(yaw_diff) <= tol and abs(pitch_diff) <= tol:
                logger.debug("camera: reached target")
                return True

            dx = round(math.degrees(-yaw_diff) * _PX_PER_DEG) if abs(yaw_diff) > tol else 0  
            dy = round(math.degrees(pitch_diff) * _PX_PER_DEG) if abs(pitch_diff) > tol else 0

            # Pick start with room for the drag, clamp to available space
            start_x, start_y = self._drag_start(yaw_diff, pitch_diff)
            bounds = self._runelite.get_game_bounds()
            if bounds is not None:
                w, h = bounds[2], bounds[3]
                max_right = w - _EDGE - start_x
                max_left = start_x - _EDGE
                dx = max(-max_left, min(max_right, dx))
                max_down = h - _EDGE - start_y
                max_up = start_y - _EDGE
                dy = max(-max_up, min(max_down, dy))

            dest_x = start_x + dx
            dest_y = start_y + dy

            # Teleport to start, hold, drag to destination
            self._mouse.move_to(start_x, start_y, linear=True)
            time.sleep(0.03)
            self._mouse.hold_middle()
            time.sleep(0.07)
            self._mouse.move_to(dest_x, dest_y, linear=True)
            time.sleep(0.1)

            # Mid-drag correction: re-check while still holding middle
            cam = self._cache.camera
            if cam is not None:
                new_yaw_diff = self._shortest_diff(target_yaw, cam.yaw) if target_yaw is not None else 0.0
                new_pitch_diff = (target_pitch - cam.pitch) if target_pitch is not None else 0.0
                yaw_done = abs(new_yaw_diff) <= tol
                pitch_done = abs(new_pitch_diff) <= tol

                if not (yaw_done and pitch_done):
                    # Fraction of original angle still remaining
                    pct_x = new_yaw_diff / yaw_diff if abs(yaw_diff) > tol else 0.0
                    pct_y = new_pitch_diff / pitch_diff if abs(pitch_diff) > tol else 0.0
                    corr_x = dest_x + round(dx * pct_x)
                    corr_y = dest_y + round(abs(dy * pct_y)) * (1 if dy > 0 else -1 if dy < 0 else 0)
                    if bounds is not None:
                        corr_x = max(_EDGE, min(w - _EDGE, corr_x))
                        corr_y = max(_EDGE, min(h - _EDGE, corr_y))
                    self._mouse.move_to(corr_x, corr_y, linear=True)
                    time.sleep(0.05)

            self._mouse.release_middle()
            time.sleep(0.035)

            # Wait for game to process before next iteration
            time.sleep(random.uniform(0.08, 0.15))

        logger.debug("camera: timeout")
        return False

    def turn_to(
        self,
        world_x: int,
        world_y: int,
        tolerance: float = 10.0,
        timeout: float = 3.0,
    ) -> bool:
        """Rotate the camera yaw to face the given world tile.

        Returns True if the camera reached the target, False on timeout.
        *tolerance* is in degrees.
        """
        angle = self._compass_angle_to(world_x, world_y)
        if angle is None:
            return False
        return self.set_angle(compass_angle=angle, tolerance=tolerance, timeout=timeout)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _yaw_to_compass(yaw_rad: float) -> float:
        """Convert OSRS yaw radians to compass degrees (0=N, 90=E)."""
        return (math.degrees(yaw_rad) + 180) % 360

    def _drag_start(self, yaw_diff: float, pitch_diff: float) -> tuple[int, int]:
        """Pick a cursor position that maximises room in the drag direction."""
        bounds = self._runelite.get_game_bounds()
        if bounds is None:
            return (400, 300)

        w, h = bounds[2], bounds[3]

        # --- horizontal ---
        if yaw_diff < 0:
            # Will drag right → start on left side
            x = random.randint(_EDGE, _EDGE + 100)
        elif yaw_diff > 0:
            # Will drag left → start on right side
            x = random.randint(w - _EDGE - 100, w - _EDGE)
        else:
            x = w // 2

        # --- vertical ---
        if pitch_diff < 0:
            # Will drag up (screen) → start lower
            y = random.randint(h - _EDGE - 100, h - _EDGE)
        elif pitch_diff > 0:
            # Will drag down (screen) → start upper
            y = random.randint(_EDGE, _EDGE + 100)
        else:
            y = h // 2

        return (x, y)

    def _compass_angle_to(self, world_x: int, world_y: int) -> float | None:
        """Compass bearing (degrees, 0=N 90=E) from the player to a tile."""
        pos = self._cache.world_position
        if pos is None or pos == (0, 0, 0):
            return None
        px, py, _ = pos
        dx = world_x - px
        dy = world_y - py
        # atan2(-dx, -dy) gives OSRS yaw; convert to compass
        yaw = math.atan2(-dx, -dy) % TWO_PI
        return self._yaw_to_compass(yaw)

    @staticmethod
    def _shortest_diff(target: float, current: float) -> float:
        """Signed shortest angular difference in radians (target - current).

        Positive → need to increase yaw (move mouse right).
        Negative → need to decrease yaw (move mouse left).
        """
        return (target - current + math.pi) % TWO_PI - math.pi
