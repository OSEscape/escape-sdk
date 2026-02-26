"""Cache for storing game state (tick, position, camera, etc.)."""

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape._proto.bridge.v1.bridge_pb2 import (  # pyright: ignore[reportMissingImports]
        CameraChanged,
        GameStateChange,
        GameTickUpdate,
    )


@dataclass(frozen=True)
class GameTickState:
    """Current game tick state."""

    tick: int
    energy: int
    scene_x: int
    scene_y: int
    target_x: int
    target_y: int
    interacting_index: int
    canvas_offset_x: int
    canvas_offset_y: int
    plane: int
    timestamp: float


@dataclass(frozen=True)
class CameraState:
    """Current camera state."""

    camera_x: int
    camera_y: int
    camera_z: int
    pitch: float
    yaw: float
    scale: int


class GameStateCache:
    """Cache for game state (tick, position, camera)."""

    def __init__(self):
        self.game_tick: GameTickState | None = None
        self.camera: CameraState | None = None
        self.game_state: str | None = None  # "LOGGED_IN", "LOGIN_SCREEN", etc.

    def process_tick(self, tick_update: GameTickUpdate) -> None:
        """Process game tick update."""
        self.game_tick = GameTickState(
            tick_update.tick,
            tick_update.energy,
            tick_update.scene_x,
            tick_update.scene_y,
            tick_update.target_x,
            tick_update.target_y,
            tick_update.interacting_index,
            tick_update.canvas_offset_x,
            tick_update.canvas_offset_y,
            tick_update.plane,
            time.time(),
        )

    def process_camera(self, camera_changed: CameraChanged) -> None:
        """Process camera change."""
        self.camera = CameraState(
            camera_changed.camera_x,
            camera_changed.camera_y,
            camera_changed.camera_z,
            camera_changed.pitch,
            camera_changed.yaw,
            camera_changed.scale,
        )

    def process_game_state(self, state_change: GameStateChange) -> None:
        """Process game state change."""
        self.game_state = state_change.state
