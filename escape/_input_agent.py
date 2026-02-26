"""Human-like mouse movement agent using Linux evdev."""

import asyncio
import contextlib
import math
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from evdev import AbsInfo, UInput
from evdev import ecodes as e

from escape._logger import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from escape.geometry import Polygon


class MovementState(Enum):
    IDLE = auto()
    MOVING = auto()
    DWELLING = auto()
    CLICKING = auto()


@dataclass
class Point:
    x: float
    y: float

    def distance_to(self, other: Point) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass
class DynamicTarget:
    """Dynamic target that can be queried during movement."""

    get_polygon: Callable[[], Polygon]  # Returns current polygon
    update_rate_hz: float = 10.0
    last_update: float = field(default=0.0, init=False)
    current_center: Point | None = field(default=None, init=False)

    def should_update(self, now: float) -> bool:
        """Check if enough time has passed for next update."""
        return (now - self.last_update) >= (1.0 / self.update_rate_hz)

    def update(self, now: float) -> Point:
        """Get fresh target point from polygon."""
        try:
            polygon = self.get_polygon()
            if len(polygon.vertices) < 3:
                return self.current_center or Point(0, 0)

            # Get centroid from polygon (returns game Point)
            center_game = polygon.center()
            # Convert to agent Point
            self.current_center = Point(float(center_game.x), float(center_game.y))
            self.last_update = now
            return self.current_center
        except Exception:
            # Polygon query failed, keep last target
            return self.current_center or Point(0, 0)


@dataclass(order=True)
class Command:
    priority: int
    deadline: float = field(compare=False)
    target: Point | None = field(compare=False, default=None)  # Optional for dynamic targets
    within_ms: int | None = field(compare=False, default=None)
    target_size: int = field(compare=False, default=30)
    callback: Callable[[], Awaitable[None]] | None = field(compare=False, default=None)
    future: asyncio.Future | None = field(compare=False, default=None)
    dynamic_target: DynamicTarget | None = field(compare=False, default=None)
    linear: bool = field(compare=False, default=False)


@dataclass
class PathPoint:
    """A single point in a pre-calculated movement path with absolute timestamp."""

    t: float  # absolute time in seconds from movement start
    x: float
    y: float
    progress: float = 0.0  # Spatial progression from origin (0.0 to 1.0)


@dataclass
class MovementPlan:
    """Pre-calculated movement path with absolute timestamps."""

    points: list[PathPoint]
    total_duration: float
    end: Point


class EvdevInput:
    """Evdev-based input device manager for mouse."""

    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        self._screen_width = screen_width
        self._screen_height = screen_height
        self._mouse: UInput | None = None

        # Initialize to actual current mouse position
        try:
            from Xlib import display

            disp = display.Display()
            data = disp.screen().root.query_pointer()._data
            disp.close()
            self._current_x = data["root_x"]
            self._current_y = data["root_y"]
        except Exception:
            self._current_x = 0
            self._current_y = 0

        self._closed = False

    def _ensure_device(self):
        if self._closed:
            raise RuntimeError("EvdevInput has been closed")

        if self._mouse is None:
            self._mouse = UInput(
                {  # pyright: ignore[reportArgumentType]
                    e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
                    e.EV_ABS: [
                        (e.ABS_X, AbsInfo(0, 0, self._screen_width - 1, 0, 0, 0)),
                        (e.ABS_Y, AbsInfo(0, 0, self._screen_height - 1, 0, 0, 0)),
                    ],
                    e.EV_REL: [e.REL_WHEEL, e.REL_HWHEEL],
                },
                name="human-mouse-agent",
            )

    @property
    def position(self) -> tuple[int, int]:
        return (self._current_x, self._current_y)

    def move_to(self, x: int, y: int):
        self._ensure_device()
        x = max(0, min(x, self._screen_width - 1))
        y = max(0, min(y, self._screen_height - 1))
        assert self._mouse is not None
        self._mouse.write(e.EV_ABS, e.ABS_X, x)
        self._mouse.write(e.EV_ABS, e.ABS_Y, y)
        self._mouse.syn()
        self._current_x = x
        self._current_y = y

    def click(self, button: int = e.BTN_LEFT):
        self._ensure_device()
        assert self._mouse is not None
        self._mouse.write(e.EV_KEY, button, 1)
        self._mouse.syn()
        time.sleep(random.uniform(0.03, 0.07))
        self._mouse.write(e.EV_KEY, button, 0)
        self._mouse.syn()

    def close(self):
        self._closed = True
        if self._mouse:
            self._mouse.close()
            self._mouse = None


class HumanMouseAgent:
    """Mouse agent with human-like movement patterns."""

    def __init__(
        self,
        polling_rate: int = 120,
        idle_enabled: bool = True,
        noise_scale: float = 1.0,
        fitts_a: float = 50,
        fitts_b: float = 150,
        screen_width: int = 1920,
        screen_height: int = 1080,
    ):
        self.polling_rate = polling_rate
        self.dt = 1.0 / polling_rate
        self.idle_enabled = idle_enabled
        self.noise_scale = noise_scale

        self._state = MovementState.IDLE
        self._queue: asyncio.PriorityQueue[Command] = asyncio.PriorityQueue()
        self._running = False
        self._lock = asyncio.Lock()

        self._evdev = EvdevInput(screen_width, screen_height)
        # Initialize to actual current mouse position
        x, y = self._evdev.position
        self._current_pos = Point(float(x), float(y))

        self._fitts_a = fitts_a
        self._fitts_b = fitts_b

        # Idle timing
        self._jitter_rate = 1 / 1.5
        self._random_move_rate = 1 / 6.0
        self._attention_factor = random.uniform(1.0, 2.0)
        self._attention_last_updated = time.time()
        self._attention_update_interval = 180

        self._idle_radius = (2, 10)

        self._command_task: asyncio.Task | None = None
        self._jitter_task: asyncio.Task | None = None
        self._random_task: asyncio.Task | None = None
        self._post_click_task: asyncio.Task | None = None

        self._last_move_start: Point | None = None
        self._last_move_end: Point | None = None

        self._post_click_probability = 0.7
        self._post_click_duration = (0.1, 0.3)

        self._random_center: Point | None = None
        self._random_std = 75

        self._idle_allowed = True
        self._idle_interrupt = False

        self.debug = False

        # Window offset for coordinate translation
        # Allows working with coordinates relative to a window
        self._offset_x = 0
        self._offset_y = 0

        # Background event loop for internal async operations
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None

    @property
    def state(self) -> MovementState:
        return self._state

    @property
    def position(self) -> Point:
        x, y = self._evdev.position
        return Point(float(x), float(y))

    def set_random_center(self, x: float | None, y: float | None):
        """Set or clear the random movement center point."""
        if x is None or y is None:
            self._random_center = None
        else:
            self._random_center = Point(float(x), float(y))

    def set_window_offset(self, x: int, y: int):
        """Set window offset for coordinate translation."""
        self._offset_x = int(x)
        self._offset_y = int(y)

    def _to_screen_coords(self, x: float, y: float) -> tuple[float, float]:
        """Convert local coordinates to screen coordinates using offset."""
        return (x + self._offset_x, y + self._offset_y)

    def _update_attention_factor(self):
        now = time.time()
        if now - self._attention_last_updated > self._attention_update_interval:
            self._attention_factor = random.uniform(1.0, 2.0)
            self._attention_last_updated = now

    def _get_idle_wait_time(self, is_random_move: bool) -> float:
        self._update_attention_factor()
        base_rate = self._random_move_rate if is_random_move else self._jitter_rate
        effective_rate = base_rate / self._attention_factor
        return random.expovariate(effective_rate)

    def _get_mouse_pos(self) -> Point:
        x, y = self._evdev.position
        return Point(float(x), float(y))

    def _generate_control_points(self, start: Point, end: Point) -> list[Point]:
        dist = start.distance_to(end)
        dx = end.x - start.x
        dy = end.y - start.y

        if dist > 0:
            perp_x = -dy / dist
            perp_y = dx / dist
        else:
            perp_x, perp_y = 0, 1

        side = random.choice([-1, 1])
        deviation_magnitude = abs(random.gauss(0, dist * 0.15)) * self.noise_scale

        t1 = 0.25 + random.gauss(0, 0.1)
        t2 = 0.75 + random.gauss(0, 0.1)

        cp1_offset = side * deviation_magnitude * random.uniform(0.8, 1.2)
        cp2_offset = side * deviation_magnitude * random.uniform(0.3, 0.7)

        cp1 = Point(
            start.x + dx * t1 + perp_x * cp1_offset,
            start.y + dy * t1 + perp_y * cp1_offset,
        )
        cp2 = Point(
            start.x + dx * t2 + perp_x * cp2_offset,
            start.y + dy * t2 + perp_y * cp2_offset,
        )

        return [start, cp1, cp2, end]

    def _bezier_point(self, control_points: list[Point], t: float) -> Point:
        p0, p1, p2, p3 = control_points
        u = 1 - t
        x = u**3 * p0.x + 3 * u**2 * t * p1.x + 3 * u * t**2 * p2.x + t**3 * p3.x
        y = u**3 * p0.y + 3 * u**2 * t * p1.y + 3 * u * t**2 * p2.y + t**3 * p3.y
        return Point(x, y)

    def _velocity_profile(self, t: float, blend: float = 0.3, time_warp: float = 1.0) -> float:
        if time_warp != 1.0:
            t = 0.5 * (2 * t) ** time_warp if t < 0.5 else 1 - 0.5 * (2 * (1 - t)) ** time_warp

        mj = 10 * t**3 - 15 * t**4 + 6 * t**5
        ss = 3 * t**2 - 2 * t**3

        return (1 - blend) * mj + blend * ss

    def _get_random_profile_params(self) -> tuple[float, float]:
        blend = random.uniform(0.25, 0.50)
        time_warp = random.uniform(0.85, 1.15)
        return blend, time_warp

    def _polygon_to_effective_width(self, polygon: Polygon) -> float:
        """Calculate effective width for Fitts' law from polygon area.

        Models polygon as circle with equivalent area:
        area = pi * r^2, diameter = 2 * sqrt(area / pi).
        Clamps to [10, 200] to keep timing reasonable.
        """
        area = polygon.area()
        if area < 1:
            return 10  # Minimum

        # Effective diameter if polygon were circular
        effective_diameter = 2 * math.sqrt(area / math.pi)

        # Clamp to reasonable range
        return max(10, min(effective_diameter, 200))

    def _calculate_movement_time(self, distance: float, target_width: float = 30) -> float:
        if distance < 1:
            return 0.05
        index_of_difficulty = math.log2(2 * distance / target_width + 1)
        mt_ms = self._fitts_a + self._fitts_b * index_of_difficulty
        mt_ms *= random.uniform(0.65, 1.35)
        return mt_ms / 1000.0

    def _plan_path_segment(
        self,
        start: Point,
        end: Point,
        duration: float,
        time_offset: float = 0.0,
        force_points: int | None = None,
        blend: float | None = None,
        time_warp: float | None = None,
    ) -> list[PathPoint]:
        control_points = self._generate_control_points(start, end)

        # Use provided params or generate new random ones
        if blend is None or time_warp is None:
            blend, time_warp = self._get_random_profile_params()

        # Use forced point count or calculate from duration
        if force_points is not None:
            num_points = force_points
        else:
            num_points = max(int(duration * self.polling_rate) + 1, 10)

        # Handle edge case: single point path
        if num_points <= 1:
            return [PathPoint(t=time_offset, x=end.x, y=end.y, progress=1.0)]

        points: list[PathPoint] = []
        for i in range(num_points):
            t_norm = i / (num_points - 1)
            t_abs = time_offset + t_norm * duration
            pos_norm = self._velocity_profile(t_norm, blend, time_warp)
            point = self._bezier_point(control_points, pos_norm)
            # pos_norm is the spatial progression along this segment
            points.append(PathPoint(t=t_abs, x=point.x, y=point.y, progress=pos_norm))

        return points

    def _plan_full_movement(
        self,
        start: Point,
        end: Point,
        duration: float,
        target_size: int = 30,
        within_ms: float | None = None,
    ) -> tuple[list[PathPoint], float, Point]:
        """Generate complete movement path with all phases (ballistic, correction, dwell)."""
        distance = start.distance_to(end)

        # Calculate natural duration
        natural_duration = self._calculate_movement_time(distance, target_width=target_size)
        natural_duration = max(natural_duration, 0.05)

        # Adjust for time constraints
        if within_ms is not None and within_ms > 0:
            requested_duration = within_ms / 1000.0
            total_duration = min(requested_duration, natural_duration)
        else:
            total_duration = duration

        # Calculate phases
        speed_factor = natural_duration / total_duration if total_duration > 0 else 1.0
        urgency = max(speed_factor, 1.0)
        attention_boost = min(urgency, 3.0)
        accuracy_multiplier = 1.0 / math.sqrt(attention_boost)

        base_spread = distance * 0.15
        spread = base_spread * accuracy_multiplier
        spread = max(spread, 2)
        spread = min(spread, 150)

        error_x = random.gauss(0, spread)
        error_y = random.gauss(0, spread)
        sampled_landing = Point(end.x + error_x, end.y + error_y)

        hit_tolerance = max(target_size * 0.5, 5)
        landing_error = sampled_landing.distance_to(end)
        will_need_correction = landing_error > hit_tolerance

        time_constrained = within_ms is not None and within_ms > 0
        skip_dwell = random.random() < 0.15

        long_pause = False
        long_pause_duration = 0.0
        if not time_constrained and random.random() < 0.10:
            long_pause = True
            long_pause_duration = random.uniform(0.4, 0.8)

        if will_need_correction:
            primary_duration = total_duration * 0.70
            correction_duration = total_duration * 0.25
            dwell_duration = total_duration * 0.05 if not skip_dwell else 0.01
            ballistic_target = sampled_landing
        else:
            if skip_dwell:
                primary_duration = total_duration * 0.95
                dwell_duration = total_duration * 0.05
            else:
                primary_duration = total_duration * 0.60
                dwell_duration = total_duration * 0.40
            correction_duration = 0
            ballistic_target = end

        primary_duration = max(primary_duration, 0.02)

        all_points: list[PathPoint] = []
        current_time = 0.0

        # Primary phase
        primary_points = self._plan_path_segment(
            start, ballistic_target, primary_duration, time_offset=current_time
        )
        all_points.extend(primary_points)
        current_time += primary_duration

        # Correction phase
        if will_need_correction and correction_duration > 0.02:
            correction_points = self._plan_path_segment(
                ballistic_target, end, correction_duration, time_offset=current_time
            )
            all_points.extend(correction_points)
            current_time += correction_duration

        # Dwell phase
        dwell_position = end if will_need_correction else ballistic_target
        if dwell_duration > 0:
            dwell_points = self._plan_dwell_segment(
                dwell_position, dwell_duration, time_offset=current_time
            )
            all_points.extend(dwell_points)
            current_time += dwell_duration

        # Long pause
        if long_pause:
            pause_points = self._plan_dwell_segment(
                end, long_pause_duration, time_offset=current_time
            )
            all_points.extend(pause_points)
            current_time += long_pause_duration

        return (all_points, total_duration, ballistic_target)

    def _recalculate_remaining_path(
        self,
        original_path: list[PathPoint],
        current_index: int,
        new_target: Point,
        movement_origin: Point,
        target_size: int = 30,
    ) -> list[PathPoint]:
        """Update remaining path by adjusting points toward new target."""
        if current_index >= len(original_path) - 1:
            return original_path  # Already at end

        remaining_old = original_path[current_index + 1 :]

        # Get original target from the last point
        old_target = Point(original_path[-1].x, original_path[-1].y)

        # Calculate direction vectors from origin
        direction_to_old = Point(old_target.x - movement_origin.x, old_target.y - movement_origin.y)
        direction_to_new = Point(new_target.x - movement_origin.x, new_target.y - movement_origin.y)

        # Avoid division by zero
        old_dist = movement_origin.distance_to(old_target)
        new_dist = movement_origin.distance_to(new_target)
        if old_dist < 1.0:
            return original_path

        # Update each remaining point using vector transformation
        updated_remaining = []
        for point in remaining_old:
            # 1. Calculate point's position relative to origin
            point_vec = Point(point.x - movement_origin.x, point.y - movement_origin.y)

            # 2. Project onto old direction to get "progress along path"
            #    This is the component in the direction of movement
            progress_along_old = (
                point_vec.x * direction_to_old.x + point_vec.y * direction_to_old.y
            ) / (old_dist * old_dist)

            # 3. Calculate perpendicular offset (preserves curve shape)
            point_along_old = Point(
                movement_origin.x + direction_to_old.x * progress_along_old,
                movement_origin.y + direction_to_old.y * progress_along_old,
            )
            perpendicular_offset = Point(point.x - point_along_old.x, point.y - point_along_old.y)

            # 4. Apply same progress to new direction
            new_position_along = Point(
                movement_origin.x + direction_to_new.x * progress_along_old,
                movement_origin.y + direction_to_new.y * progress_along_old,
            )

            # 5. Reapply perpendicular offset to preserve curve
            #    Scale offset if target distance changed significantly
            scale_factor = new_dist / old_dist if old_dist > 0 else 1.0
            scale_factor = max(0.5, min(scale_factor, 2.0))  # Clamp scaling

            final_position = Point(
                new_position_along.x + perpendicular_offset.x * scale_factor,
                new_position_along.y + perpendicular_offset.y * scale_factor,
            )

            # 6. Create updated point with SAME TIMESTAMP (preserves velocity)
            updated_remaining.append(
                PathPoint(
                    t=point.t, x=final_position.x, y=final_position.y, progress=point.progress
                )
            )

        logger.debug(
            f"[Replan] Updated {len(updated_remaining)} points via vector transform "
            f"(old_dist={old_dist:.1f}px, new_dist={new_dist:.1f}px)"
        )

        # Return original path up to current + updated remaining
        return original_path[: current_index + 1] + updated_remaining

    def _plan_dwell_segment(
        self,
        position: Point,
        duration: float,
        time_offset: float = 0.0,
    ) -> list[PathPoint]:
        if duration <= 0:
            return []
        return [
            PathPoint(t=time_offset, x=position.x, y=position.y),
            PathPoint(t=time_offset + duration, x=position.x, y=position.y),
        ]

    def _plan_path(
        self,
        start: Point,
        end: Point,
        duration: float,
    ) -> MovementPlan:
        points = self._plan_path_segment(start, end, duration, time_offset=0.0)
        return MovementPlan(points=points, total_duration=duration, end=end)

    async def _execute_plan(
        self,
        plan: MovementPlan,
        check_interrupt: bool = False,
    ) -> bool:
        if not plan.points:
            return True

        start_time = time.perf_counter()

        for point in plan.points:
            if check_interrupt and self._idle_interrupt:
                return False

            now = time.perf_counter()
            elapsed = now - start_time
            wait_time = point.t - elapsed

            if wait_time > 0.001:
                await asyncio.sleep(wait_time)

            self._evdev.move_to(int(point.x), int(point.y))
            self._current_pos = Point(point.x, point.y)

        self._evdev.move_to(int(plan.end.x), int(plan.end.y))
        self._current_pos = plan.end

        return True

    async def _execute_linear_movement(
        self,
        target: Point,
    ) -> tuple[float, float, int]:
        """Move to target in a straight line. Disables idle until next click."""
        t0 = time.perf_counter()

        if self._post_click_task and not self._post_click_task.done():
            self._post_click_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._post_click_task

        self._idle_interrupt = True

        async with self._lock:
            self._idle_interrupt = False
            self._state = MovementState.MOVING

            start = self._get_mouse_pos()
            distance = start.distance_to(target)
            duration = max(distance / 800.0, 0.02)  # ~800 px/s, min 20ms
            num_points = max(int(duration * self.polling_rate) + 1, 3)

            points: list[PathPoint] = []
            for i in range(num_points):
                t_norm = i / (num_points - 1)
                points.append(PathPoint(
                    t=t_norm * duration,
                    x=start.x + (target.x - start.x) * t_norm,
                    y=start.y + (target.y - start.y) * t_norm,
                    progress=t_norm,
                ))

            plan = MovementPlan(points=points, total_duration=duration, end=target)
            await self._execute_plan(plan)

            self._state = MovementState.IDLE
            self._idle_allowed = False
            actual_ms = int((time.perf_counter() - t0) * 1000)
            return (self._current_pos.x, self._current_pos.y, actual_ms)

    async def _execute_movement(
        self,
        target: Point | None = None,
        dynamic_target: DynamicTarget | None = None,
        within_ms: float | None = None,
        target_size: int = 30,
    ) -> tuple[float, float, int]:
        """Execute movement with optional dynamic target tracking."""
        if target is None and dynamic_target is None:
            raise ValueError("Must provide either target or dynamic_target")

        t0 = time.perf_counter()

        # Cancel post-click task
        if self._post_click_task and not self._post_click_task.done():
            self._post_click_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._post_click_task

        self._idle_interrupt = True

        async with self._lock:
            self._idle_interrupt = False
            self._state = MovementState.MOVING

            # Get initial target and store movement origin
            start = self._get_mouse_pos()
            movement_origin = start  # Store the original start position for absolute progression
            if dynamic_target:
                current_target = dynamic_target.update(time.perf_counter())
            else:
                assert target is not None  # Validated at function start
                current_target = target

            distance = start.distance_to(current_target)
            self._last_move_start = start
            self._last_move_end = current_target

            # Calculate duration
            natural_duration = self._calculate_movement_time(distance, target_width=target_size)
            natural_duration = max(natural_duration, 0.05)

            if within_ms is not None and within_ms > 0:
                requested_duration = within_ms / 1000.0
                total_duration = min(requested_duration, natural_duration)
            else:
                total_duration = natural_duration

            # Debug output
            label = "Dynamic" if dynamic_target else "Static"
            # logger.debug(
            #     f"[Movement Init - {label}] start=({start.x:.0f}, {start.y:.0f}) "
            #     f"target=({current_target.x:.0f}, {current_target.y:.0f}) "
            #     f"dist={distance:.1f}px size={target_size}px "
            #     f"natural={natural_duration * 1000:.0f}ms "
            #     f"requested={within_ms if within_ms else 'None'}ms "
            #     f"final={total_duration * 1000:.0f}ms"
            # )

            # Plan full path using the new helper
            all_points, total_duration, _ballistic_target = self._plan_full_movement(
                start=start,
                end=current_target,
                duration=total_duration,
                target_size=target_size,
                within_ms=within_ms,
            )

            # Debug path output
            if all_points:
                mid = len(all_points) // 2
                # logger.debug(
                #     f"[Path Plan] {len(all_points)} points: "
                #     f"first=t={all_points[0].t * 1000:.0f}ms ({all_points[0].x:.0f}, {all_points[0].y:.0f}) "
                #     f"mid=t={all_points[mid].t * 1000:.0f}ms ({all_points[mid].x:.0f}, {all_points[mid].y:.0f}) "
                #     f"last=t={all_points[-1].t * 1000:.0f}ms ({all_points[-1].x:.0f}, {all_points[-1].y:.0f})"
                # )
            else:
                logger.debug("[Path Plan] 0 points")

            movement_start = time.perf_counter()
            replan_count = 0
            max_replans = 50  # Safety limit for extreme cases
            max_duration = max(total_duration * 3.0, 0.1)  # Emergency timeout, floor at 100ms for overhead

            # Execute path point by point
            i = 0
            iteration = 0
            while i < len(all_points):
                iteration += 1

                # Emergency escape hatches
                if iteration > 1000:
                    logger.error(
                        f"[Mouse Agent] Infinite loop detected! i={i}, len={len(all_points)}"
                    )
                    break

                elapsed_total = time.perf_counter() - movement_start
                if elapsed_total > max_duration:
                    logger.error(
                        f"[Mouse Agent] Movement exceeded max duration ({max_duration:.1f}s), aborting"
                    )
                    break

                point = all_points[i]

                # Dynamic-only: Check if target moved
                if dynamic_target:
                    try:
                        check_start = time.perf_counter()
                        new_target = dynamic_target.update(time.perf_counter())
                        check_time = (time.perf_counter() - check_start) * 1000
                    except Exception as e:
                        logger.error(f"[Mouse Agent] Error during target update: {e}")
                        break

                    # Replan if target moved at all (no threshold needed with absolute progression!)
                    if (
                        new_target.distance_to(current_target) > 1.0
                    ):  # Just to avoid floating point noise
                        if replan_count >= max_replans:
                            logger.debug(
                                f"[Mouse Agent] Max replans ({max_replans}) reached, continuing with current path"
                            )
                        else:
                            try:
                                replan_start = time.perf_counter()
                                old_len = len(all_points)
                                all_points = self._recalculate_remaining_path(
                                    all_points,
                                    i,
                                    new_target,
                                    movement_origin,  # NEW: pass the origin
                                    target_size,  # NEW: pass target size
                                )
                                new_len = len(all_points)
                                replan_time = (time.perf_counter() - replan_start) * 1000
                                replan_count += 1
                                logger.debug(
                                    f"[Mouse Agent] Target moved, replanned in {replan_time:.1f}ms (replan #{replan_count}, i={i}, len {old_len}->{new_len}, check took {check_time:.1f}ms)"
                                )
                                current_target = new_target
                                self._last_move_end = current_target
                                # Path updated, fetch updated current point
                                point = all_points[i]
                            except Exception as e:
                                logger.error(f"[Mouse Agent] Error during replan: {e}")
                                break

                # Execute point at scheduled time
                elapsed = time.perf_counter() - movement_start
                wait_time = point.t - elapsed
                if wait_time > 0.001:
                    await asyncio.sleep(wait_time)

                self._evdev.move_to(int(point.x), int(point.y))
                self._current_pos = Point(point.x, point.y)

                # Periodic progress output (every 10th point)
                if dynamic_target and i % 10 == 0:
                    temporal_progress = point.t / all_points[-1].t if all_points[-1].t > 0 else 0.0
                    logger.debug(
                        f"[t={point.t * 1000:.0f}ms] temporal={temporal_progress:.1%}, pos=({point.x:.0f}, {point.y:.0f})"
                    )

                i += 1

            actual_duration_ms = int((time.perf_counter() - t0) * 1000)

            logger.debug(
                f"[Movement Complete - {label}] planned={total_duration * 1000:.0f}ms "
                f"actual={actual_duration_ms}ms diff={actual_duration_ms - total_duration * 1000:.0f}ms"
            )

            self._state = MovementState.IDLE
            self._idle_allowed = False
            return (self._current_pos.x, self._current_pos.y, actual_duration_ms)

    async def _click_async(self, button: str = "left") -> tuple[float, float]:
        if self._post_click_task and not self._post_click_task.done():
            self._post_click_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._post_click_task

        self._state = MovementState.CLICKING
        pos = self._get_mouse_pos()

        button_map = {"left": e.BTN_LEFT, "right": e.BTN_RIGHT, "middle": e.BTN_MIDDLE}
        btn = button_map.get(button, e.BTN_LEFT)
        self._evdev.click(btn)

        await asyncio.sleep(0.050)
        self._current_pos = pos

        self._state = MovementState.IDLE
        if button == "left":
            self._idle_allowed = True

        if self.idle_enabled and self._idle_allowed and random.random() < self._post_click_probability:
            self._post_click_task = asyncio.create_task(self._post_click_movement())

        return (pos.x, pos.y)

    async def _post_click_movement(self):
        try:
            if self._idle_interrupt:
                return

            current = self._get_mouse_pos()

            if self._last_move_start and self._last_move_end:
                move_distance = self._last_move_start.distance_to(self._last_move_end)

                if random.random() < 0.6:
                    center_x = (self._last_move_start.x + self._last_move_end.x) / 2
                    center_y = (self._last_move_start.y + self._last_move_end.y) / 2
                    std_dev = max(move_distance / 3, 2)
                    std_dev = min(std_dev, 40)
                else:
                    center_x = self._last_move_end.x
                    center_y = self._last_move_end.y
                    std_dev = 15
            else:
                center_x = current.x
                center_y = current.y
                std_dev = 5

            target = Point(
                center_x + random.gauss(0, std_dev),
                center_y + random.gauss(0, std_dev),
            )

            duration = random.uniform(*self._post_click_duration)
            plan = self._plan_path(current, target, duration)

            delay = random.expovariate(1 / 0.1)
            if delay > 0.3:
                return

            await asyncio.sleep(delay)

            if self._idle_interrupt:
                return

            async with self._lock:
                if self._idle_interrupt:
                    return
                self._state = MovementState.MOVING
                await self._execute_plan(plan, check_interrupt=True)
                self._state = MovementState.IDLE

        except asyncio.CancelledError:
            self._state = MovementState.IDLE
            raise

    async def _jitter_loop(self):
        while self._running:
            try:
                if self._state == MovementState.IDLE and self.idle_enabled and self._idle_allowed:
                    wait = self._get_idle_wait_time(is_random_move=False)
                    wait = min(wait, 10.0)
                    await asyncio.sleep(wait)
                    if self._state == MovementState.IDLE and self._idle_allowed:
                        await self._idle_micro_movement()
                else:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break

    async def _random_loop(self):
        while self._running:
            try:
                if (
                    self._state == MovementState.IDLE
                    and self.idle_enabled
                    and self._idle_allowed
                    and self._random_center is not None
                ):
                    wait = self._get_idle_wait_time(is_random_move=True)
                    wait = min(wait, 15.0)
                    await asyncio.sleep(wait)
                    if (
                        self._state == MovementState.IDLE
                        and self._idle_allowed
                        and self._random_center is not None
                    ):
                        await self._random_movement()
                else:
                    await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                break

    async def _random_movement(self):
        if self._state != MovementState.IDLE or self._random_center is None:
            return
        if self._idle_interrupt:
            return

        # Convert random center from window-relative to screen coordinates
        center_screen_x, center_screen_y = self._to_screen_coords(
            self._random_center.x, self._random_center.y
        )

        target = Point(
            center_screen_x + random.gauss(0, self._random_std),
            center_screen_y + random.gauss(0, self._random_std),
        )

        start = self._current_pos
        distance = start.distance_to(target)
        duration = self._calculate_movement_time(distance)
        duration = max(duration, 0.1)

        plan = self._plan_path(start, target, duration)

        async with self._lock:
            if self._idle_interrupt:
                self._state = MovementState.IDLE
                return
            self._state = MovementState.MOVING
            await self._execute_plan(plan, check_interrupt=True)
            self._state = MovementState.IDLE

    async def _idle_micro_movement(self):
        if self._state != MovementState.IDLE:
            return
        if self._idle_interrupt:
            return

        radius = random.uniform(*self._idle_radius)
        angle = random.uniform(0, 2 * math.pi)
        start = self._current_pos
        target = Point(
            start.x + radius * math.cos(angle),
            start.y + radius * math.sin(angle),
        )
        duration = random.uniform(0.1, 0.3)

        plan = self._plan_path(start, target, duration)

        async with self._lock:
            if self._idle_interrupt:
                self._state = MovementState.IDLE
                return
            self._state = MovementState.MOVING
            await self._execute_plan(plan, check_interrupt=True)
            self._state = MovementState.IDLE

    async def _command_loop(self):
        while self._running:
            try:
                cmd = await asyncio.wait_for(self._queue.get(), timeout=0.1)

                # Dispatch movement
                if cmd.linear and cmd.target is not None:
                    x, y, duration_ms = await self._execute_linear_movement(
                        target=cmd.target,
                    )
                elif cmd.target is not None or cmd.dynamic_target is not None:
                    x, y, duration_ms = await self._execute_movement(
                        target=cmd.target,
                        dynamic_target=cmd.dynamic_target,
                        within_ms=cmd.within_ms if cmd.within_ms and cmd.within_ms > 0 else None,
                        target_size=cmd.target_size,
                    )
                else:
                    # Invalid command, skip
                    self._queue.task_done()
                    continue

                if cmd.future and not cmd.future.done():
                    cmd.future.set_result((x, y, duration_ms))

                if cmd.callback:
                    await cmd.callback()

                self._queue.task_done()

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def _start_async(self):
        if self._running:
            return
        self._running = True
        self._current_pos = self._get_mouse_pos()
        self._command_task = asyncio.create_task(self._command_loop())
        self._jitter_task = asyncio.create_task(self._jitter_loop())
        self._random_task = asyncio.create_task(self._random_loop())

    async def _stop_async(self):
        if not self._running:
            return
        self._running = False
        tasks = []
        if self._command_task:
            self._command_task.cancel()
            tasks.append(self._command_task)
        if self._jitter_task:
            self._jitter_task.cancel()
            tasks.append(self._jitter_task)
        if self._random_task:
            self._random_task.cancel()
            tasks.append(self._random_task)
        if self._post_click_task and not self._post_click_task.done():
            self._post_click_task.cancel()
            tasks.append(self._post_click_task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._evdev.close()

    # ─────────────────────────────────────────────────────────
    # Public Sync API
    # ─────────────────────────────────────────────────────────

    def _ensure_loop(self):
        """Start background event loop if not running."""
        if self._loop is not None and self._loop.is_running():
            return

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        while self._loop is None or not self._loop.is_running():
            time.sleep(0.01)

    def start(self):
        """Start the agent."""
        self._ensure_loop()
        assert self._loop is not None
        future = asyncio.run_coroutine_threadsafe(self._start_async(), self._loop)
        future.result(timeout=5.0)

    def stop(self):
        """Stop the agent."""
        if self._loop is not None and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._stop_async(), self._loop)
            future.result(timeout=5.0)
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread:
                self._loop_thread.join(timeout=2.0)
            self._loop = None
            self._loop_thread = None

    def move_to(
        self,
        x: float | None = None,
        y: float | None = None,
        within_ms: int | None = None,
        target_size: int = 30,
        timeout: float = 10.0,
        polygon: Callable[[], Polygon] | None = None,
        update_rate_hz: float = 100.0,
        linear: bool = False,
    ) -> tuple[float, float, int]:
        """Move to target position. Use linear=True for straight-line movement."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("Agent not started. Use 'with' statement or call start().")

        loop = self._loop

        async def create_future_coro() -> asyncio.Future[tuple[float, float, int]]:
            return loop.create_future()  # type: ignore

        future: asyncio.Future[tuple[float, float, int]] = asyncio.run_coroutine_threadsafe(
            create_future_coro(), loop
        ).result()

        deadline = time.time() + (within_ms / 1000.0 if within_ms and within_ms > 0 else 10.0)

        if polygon is not None:
            try:
                initial_poly = polygon()
                effective_size = int(self._polygon_to_effective_width(initial_poly))
            except Exception:
                effective_size = 30

            def offset_polygon_callable() -> Polygon:
                from escape.geometry import Polygon as GamePolygon
                from escape.point import ScreenPoint

                poly = polygon()
                offset_vertices = [
                    ScreenPoint(int(v.x + self._offset_x), int(v.y + self._offset_y))
                    for v in poly.vertices
                ]
                return GamePolygon(vertices=offset_vertices)

            dynamic_target = DynamicTarget(
                get_polygon=offset_polygon_callable,
                update_rate_hz=update_rate_hz,
            )

            cmd = Command(
                priority=1,
                deadline=deadline,
                target=None,
                within_ms=within_ms if within_ms and within_ms > 0 else None,
                target_size=effective_size,
                future=future,
                dynamic_target=dynamic_target,
            )
        else:
            if x is None or y is None:
                raise ValueError("Must provide either (x, y) or polygon")

            screen_x, screen_y = self._to_screen_coords(x, y)

            cmd = Command(
                priority=1,
                deadline=deadline,
                target=Point(float(screen_x), float(screen_y)),
                within_ms=within_ms if within_ms and within_ms > 0 else None,
                target_size=target_size,
                future=future,
                dynamic_target=None,
                linear=linear,
            )

        asyncio.run_coroutine_threadsafe(self._queue.put(cmd), loop)

        return asyncio.run_coroutine_threadsafe(
            asyncio.wait_for(future, timeout=timeout), loop
        ).result(timeout=timeout + 1)

    def click(self, button: str = "left", timeout: float = 5.0) -> tuple[float, float]:
        """Click at current position."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("Agent not started. Use 'with' statement or call start().")

        future = asyncio.run_coroutine_threadsafe(self._click_async(button), self._loop)
        return future.result(timeout=timeout)

    async def _scroll_async(self, clicks: int) -> None:
        """Async scroll implementation."""
        self._state = MovementState.CLICKING

        direction = 1 if clicks > 0 else -1
        for _ in range(abs(clicks)):
            self._evdev._ensure_device()
            assert self._evdev._mouse is not None
            self._evdev._mouse.write(e.EV_REL, e.REL_WHEEL, direction)
            self._evdev._mouse.syn()
            await asyncio.sleep(0.02)

        self._state = MovementState.IDLE

    def scroll(self, up: bool = True, count: int = 1, timeout: float = 5.0) -> None:
        """Scroll the mouse wheel."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("Agent not started.")

        clicks = count if up else -count
        future = asyncio.run_coroutine_threadsafe(self._scroll_async(clicks), self._loop)
        future.result(timeout=timeout)

    async def _hold_async(self, button: str) -> None:
        """Async hold implementation."""
        button_map = {"left": e.BTN_LEFT, "right": e.BTN_RIGHT, "middle": e.BTN_MIDDLE}
        btn = button_map.get(button, e.BTN_LEFT)

        self._evdev._ensure_device()
        assert self._evdev._mouse is not None
        self._evdev._mouse.write(e.EV_KEY, btn, 1)
        self._evdev._mouse.syn()

    async def _release_async(self, button: str) -> None:
        """Async release implementation."""
        button_map = {"left": e.BTN_LEFT, "right": e.BTN_RIGHT, "middle": e.BTN_MIDDLE}
        btn = button_map.get(button, e.BTN_LEFT)

        self._evdev._ensure_device()
        assert self._evdev._mouse is not None
        self._evdev._mouse.write(e.EV_KEY, btn, 0)
        self._evdev._mouse.syn()

    def hold(self, button: str = "left", timeout: float = 5.0) -> None:
        """Hold mouse button down."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("Agent not started.")

        future = asyncio.run_coroutine_threadsafe(self._hold_async(button), self._loop)
        future.result(timeout=timeout)

    def release(self, button: str = "left", timeout: float = 5.0) -> None:
        """Release mouse button."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("Agent not started.")

        future = asyncio.run_coroutine_threadsafe(self._release_async(button), self._loop)
        future.result(timeout=timeout)

    async def _teleport_async(self, x: float, y: float) -> None:
        """Jump cursor to (x, y) immediately, no path planning."""
        self._idle_interrupt = True
        async with self._lock:
            self._idle_interrupt = False
            sx, sy = self._to_screen_coords(x, y)
            self._evdev.move_to(int(sx), int(sy))
            self._current_pos = Point(x, y)
            self._idle_allowed = False

    def teleport(self, x: float, y: float, timeout: float = 5.0) -> None:
        """Teleport cursor to screen coordinates, bypassing path planning."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("Agent not started.")

        future = asyncio.run_coroutine_threadsafe(
            self._teleport_async(x, y), self._loop
        )
        future.result(timeout=timeout)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
