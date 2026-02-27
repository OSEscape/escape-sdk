"""Input module: RuneLite window management, mouse, and keyboard."""

from __future__ import annotations

import contextlib
import random
import subprocess
import threading
import time
from typing import TYPE_CHECKING, Any

from evdev import UInput
from evdev import ecodes as e
from Xlib import X, display

from escape.geometry import Box

if TYPE_CHECKING:
    from collections.abc import Callable

    from escape._input_agent import HumanMouseAgent
    from escape.geometry import Polygon

# ---------------------------------------------------------------------------
# RuneLite window tracker
# ---------------------------------------------------------------------------


class RuneLite:
    """RuneLite window position tracker using X11 events."""

    def __init__(self, window_title: str = "RuneLite", auto_refresh: bool = True):
        self.window_title = window_title
        self.auto_refresh = auto_refresh

        self._window_id: int | None = None
        self._window_offset: tuple[int, int] | None = None
        self._window_size: tuple[int, int] | None = None
        self._is_minimized: bool = False
        self._is_active: bool = False
        self._state_valid: bool = False

        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self._display: display.Display | None = None
        self._event_thread: threading.Thread | None = None
        self._needs_refresh: bool = True

        self._initialize_display()
        self.detect_window()

        if self._window_id:
            self._start_event_listener()

    def _initialize_display(self) -> bool:
        try:
            self._display = display.Display()
            return True
        except Exception:
            self._display = None
            return False

    def _start_event_listener(self) -> None:
        if self._event_thread is not None and self._event_thread.is_alive():
            return

        self._stop_event.clear()
        self._event_thread = threading.Thread(target=self._event_loop, daemon=True)
        self._event_thread.start()

    def _stop_event_listener(self) -> None:
        self._stop_event.set()
        if self._event_thread is not None:
            self._event_thread.join(timeout=1.0)
            self._event_thread = None

    def _event_loop(self) -> None:
        try:
            event_display = display.Display()
            root = event_display.screen().root
            root.change_attributes(event_mask=X.PropertyChangeMask)

            if self._window_id:
                try:
                    window = event_display.create_resource_object("window", self._window_id)
                    window.change_attributes(
                        event_mask=(
                            X.StructureNotifyMask
                            | X.FocusChangeMask
                            | X.PropertyChangeMask
                            | X.VisibilityChangeMask
                        )
                    )
                except Exception:
                    pass

            while not self._stop_event.is_set():
                if event_display.pending_events() > 0:
                    evt = event_display.next_event()
                    self._handle_event(evt, event_display)
                else:
                    time.sleep(0.01)

            event_display.close()

        except Exception:
            with self._lock:
                self._state_valid = False

    def _handle_event(self, evt: Any, event_display: display.Display) -> None:
        with self._lock:
            if evt.type == X.ConfigureNotify:
                if hasattr(evt, "window") and evt.window:
                    window_id = evt.window.id if hasattr(evt.window, "id") else evt.window
                    if window_id == self._window_id:
                        self._needs_refresh = True
                        # Update size immediately from event if possible
                        if hasattr(evt, "width") and hasattr(evt, "height"):
                            self._window_size = (evt.width, evt.height)

            elif evt.type == X.UnmapNotify:
                if hasattr(evt, "window") and evt.window:
                    window_id = evt.window.id if hasattr(evt.window, "id") else evt.window
                    if window_id == self._window_id:
                        self._is_minimized = True

            elif evt.type == X.MapNotify:
                if hasattr(evt, "window") and evt.window:
                    window_id = evt.window.id if hasattr(evt.window, "id") else evt.window
                    if window_id == self._window_id:
                        self._is_minimized = False

            elif evt.type == X.FocusIn:
                if hasattr(evt, "window") and evt.window:
                    window_id = evt.window.id if hasattr(evt.window, "id") else evt.window
                    if window_id == self._window_id:
                        self._is_active = True

            elif evt.type == X.FocusOut:
                if hasattr(evt, "window") and evt.window:
                    window_id = evt.window.id if hasattr(evt.window, "id") else evt.window
                    if window_id == self._window_id:
                        self._is_active = False

            elif evt.type == X.PropertyNotify and hasattr(evt, "atom"):
                atom_name = event_display.get_atom_name(evt.atom)
                if atom_name == "_NET_ACTIVE_WINDOW":
                    self._update_active_state(event_display)

    def _update_active_state(self, event_display: display.Display) -> None:
        try:
            root = event_display.screen().root
            atom = event_display.intern_atom("_NET_ACTIVE_WINDOW")
            response = root.get_full_property(atom, X.AnyPropertyType)

            if response and response.value:
                active_id = response.value[0]
                self._is_active = active_id == self._window_id
        except Exception:
            pass

    def detect_window(self) -> bool:
        """Detect the RuneLite window via xwininfo/xprop and populate position state."""
        try:
            # Find window ID using xdotool or xwininfo search
            search_res = subprocess.run(
                ["xdotool", "search", "--name", f"^{self.window_title}"],
                capture_output=True,
                text=True,
                check=False,
            )

            window_ids = search_res.stdout.strip().split("\n")
            target_id = None

            for wid_str in window_ids:
                if not wid_str:
                    continue
                wid = int(wid_str)
                # Verify it's actually RuneLite and not a browser tab or similar
                prop_res = subprocess.run(
                    ["xprop", "-id", str(wid), "WM_CLASS"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if "runelite" in prop_res.stdout.lower():
                    target_id = wid
                    break

            if target_id is None:
                # Fallback: try finding by name directly with xwininfo
                info_res = subprocess.run(
                    ["xwininfo", "-name", self.window_title],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if info_res.returncode == 0:
                    for line in info_res.stdout.split("\n"):
                        if "Window id:" in line:
                            target_id = int(line.split()[3], 16)
                            break

            if target_id is None:
                return False

            # Get detailed geometry
            geom_res = subprocess.run(
                ["xwininfo", "-id", str(target_id)],
                capture_output=True,
                text=True,
                check=False,
            )

            if geom_res.returncode != 0:
                return False

            x, y, width, height = 0, 0, 0, 0
            is_minimized = "IsUnMapped" in geom_res.stdout

            for line in geom_res.stdout.split("\n"):
                line = line.strip()
                if line.startswith("Absolute upper-left X:"):
                    x = int(line.split(":")[1].strip())
                elif line.startswith("Absolute upper-left Y:"):
                    y = int(line.split(":")[1].strip())
                elif line.startswith("Width:"):
                    width = int(line.split(":")[1].strip())
                elif line.startswith("Height:"):
                    height = int(line.split(":")[1].strip())

            with self._lock:
                self._window_id = target_id
                self._window_offset = (x, y)
                self._window_size = (width, height)
                self._is_minimized = is_minimized
                self._state_valid = True

            self._check_active_state()
            self._start_event_listener()
            return True

        except Exception as e:
            from escape._logger import logger

            logger.error(f"Failed to detect window: {e}")
            return False

    def _check_active_state(self) -> None:
        if self._display is None or self._window_id is None:
            return

        try:
            root = self._display.screen().root
            atom = self._display.intern_atom("_NET_ACTIVE_WINDOW")
            response = root.get_full_property(atom, X.AnyPropertyType)

            if response and response.value:
                active_id = response.value[0]
                with self._lock:
                    self._is_active = active_id == self._window_id
        except Exception:
            pass

    def activate_window(self) -> bool:
        """Bring the RuneLite window to the foreground."""
        if self._window_id is None and not self.detect_window():
            return False
        if self._window_id is None:
            return False

        try:
            window_id_hex = hex(self._window_id)

            subprocess.run(
                ["xdotool", "windowmap", window_id_hex], capture_output=True, check=False
            )
            subprocess.run(
                ["xdotool", "windowactivate", window_id_hex], capture_output=True, check=False
            )

            time.sleep(0.1)

            if self._window_size:
                w, h = self._window_size
                pt = Box(4, 4, w - 8, h - 8).random_point()
                subprocess.run(
                    ["xdotool", "mousemove", str(pt.x), str(pt.y)],
                    capture_output=True,
                    check=False,
                )

            with self._lock:
                self._is_minimized = False
                self._is_active = True

            self.detect_window()

            return True

        except Exception:
            return False

    def is_window_minimized(self) -> bool:
        """Return whether the RuneLite window is minimized."""
        with self._lock:
            return self._is_minimized

    def is_window_active(self) -> bool:
        """Return whether the RuneLite window has focus."""
        with self._lock:
            return self._is_active

    def ensure_window_ready(self) -> bool:
        """Ensure the RuneLite window is visible and focused."""
        with self._lock:
            if not self._state_valid:
                pass
            elif not self._is_minimized and self._is_active:
                return True

        if not self._state_valid and not self.detect_window():
            return False

        if self._is_minimized or not self._is_active:
            return self.activate_window()

        return True

    def refresh_window_position(self, force: bool = False, max_age: float = 10.0) -> bool:
        """Refresh the cached window position, re-detecting if stale."""
        with self._lock:
            if (
                not force
                and not self._needs_refresh
                and self._state_valid
                and not self._is_minimized
                and self._is_active
            ):
                return True

        return self.ensure_window_ready()

    def _auto_refresh(self) -> None:
        if self.auto_refresh:
            self.refresh_window_position()

    def get_window_offset(self) -> tuple[int, int] | None:
        """Top-left (x, y) offset of the RuneLite window."""
        self._auto_refresh()
        with self._lock:
            return self._window_offset

    def get_window_size(self) -> tuple[int, int] | None:
        """Width and height of the RuneLite window."""
        self._auto_refresh()
        with self._lock:
            return self._window_size

    def get_game_bounds(self) -> tuple[int, int, int, int] | None:
        """Bounding rectangle (x, y, width, height) of the game area."""
        self._auto_refresh()

        with self._lock:
            if self._window_offset and self._window_size:
                return (
                    self._window_offset[0],
                    self._window_offset[1],
                    self._window_size[0],
                    self._window_size[1],
                )
        return None

    def set_minimized(self, minimized: bool) -> None:
        """Set the minimized state flag."""
        with self._lock:
            self._is_minimized = minimized

    def set_active(self, active: bool) -> None:
        """Set the active/focused state flag."""
        with self._lock:
            self._is_active = active

    def __del__(self):
        self._stop_event_listener()
        if self._display:
            with contextlib.suppress(Exception):
                self._display.close()


# ---------------------------------------------------------------------------
# Mouse
# ---------------------------------------------------------------------------


def _get_screen_size() -> tuple[int, int]:
    try:
        result = subprocess.run(["xrandr"], capture_output=True, text=True, timeout=2)
        for line in result.stdout.split("\n"):
            if " connected" in line and "primary" in line:
                parts = line.split()
                for part in parts:
                    if "x" in part and "+" in part:
                        res = part.split("+")[0]
                        w, h = res.split("x")
                        return (int(w), int(h))
        for line in result.stdout.split("\n"):
            if " connected" in line:
                parts = line.split()
                for part in parts:
                    if "x" in part and "+" in part:
                        res = part.split("+")[0]
                        w, h = res.split("x")
                        return (int(w), int(h))
    except Exception:
        pass
    return (1920, 1080)


class Mouse:
    """Mouse controller with human-like movement."""

    def __init__(self, runelite: RuneLite, cache: Any = None, speed: float = 1.0):
        self.runelite = runelite
        self.cache = cache
        self.speed = speed
        self._agent: HumanMouseAgent | None = None
        self._agent_started = False

    def _ensure_agent(self) -> None:
        from escape._input_agent import HumanMouseAgent

        if self._agent is not None and self._agent_started:
            return

        if self._agent is None:
            screen_w, screen_h = _get_screen_size()

            self._agent = HumanMouseAgent(
                screen_width=screen_w,
                screen_height=screen_h,
                polling_rate=60,
                idle_enabled=True,
                noise_scale=1.0,
                fitts_a=0,
                fitts_b=150,
            )

        if not self._agent_started:
            self._agent.start()
            self._agent_started = True

            self._update_window_offset()
            self._update_random_center()

    @property
    def _a(self) -> HumanMouseAgent:
        self._ensure_agent()
        assert self._agent is not None
        return self._agent

    def _update_window_offset(self) -> None:
        offset = self.runelite.get_window_offset()
        if offset and self._agent:
            self._agent.set_window_offset(offset[0], offset[1])

    def _update_random_center(self) -> None:
        if not self._agent:
            return
        bounds = self.runelite.get_game_bounds()
        if bounds:
            center_x = bounds[2] / 2
            center_y = bounds[3] / 2
            self._agent.set_random_center(center_x, center_y)

    @property
    def position(self) -> tuple[int, int]:
        """Current mouse position relative to the game window."""
        x, y = 0, 0
        if self._agent and self._agent_started:
            screen_pos = self._agent.position
            offset = self.runelite.get_window_offset()
            if offset:
                x, y = (int(screen_pos.x - offset[0]), int(screen_pos.y - offset[1]))
            else:
                x, y = (int(screen_pos.x), int(screen_pos.y))
        else:
            disp = display.Display()
            data = disp.screen().root.query_pointer()._data
            disp.close()
            offset = self.runelite.get_window_offset()
            if offset:
                x, y = (data["root_x"] - offset[0], data["root_y"] - offset[1])
            else:
                x, y = (data["root_x"], data["root_y"])

        if self.cache:
            cx, cy = self.cache.canvas_offset
            x -= cx
            y -= cy
        return (x, y)

    def _prepare(self) -> None:
        self._ensure_agent()
        self.runelite.refresh_window_position()
        self._update_window_offset()
        self._update_random_center()

    def _make_offset_polygon(self, polygon: Callable[[], Polygon]) -> Callable[[], Polygon]:
        def offset_polygon() -> Polygon:
            from escape.geometry import Polygon as GamePolygon
            from escape.point import ScreenPoint

            poly = polygon()
            if not self.cache:
                return poly
            cx, cy = self.cache.canvas_offset
            return GamePolygon(
                vertices=[ScreenPoint(int(v.x + cx), int(v.y + cy)) for v in poly.vertices]
            )

        return offset_polygon

    def _move_to(
        self,
        x: int,
        y: int,
        within_ms: int | None = None,
        linear: bool = False,
    ) -> None:
        self._prepare()

        if self.cache:
            cx, cy = self.cache.canvas_offset
            x += cx
            y += cy

        self._a.move_to(
            float(x),
            float(y),
            within_ms=within_ms,
            target_size=30,
            linear=linear,
        )

    def _click_button(self, button: str) -> None:
        self._prepare()
        self._a.click(button=button)

    def _hold(self, button: str) -> None:
        self._prepare()
        self._a.hold(button=button)

    def _release(self, button: str) -> None:
        self._prepare()
        self._a.release(button=button)

    def _scroll(self, clicks: int) -> None:
        self._prepare()
        up = clicks > 0
        count = abs(clicks)
        self._a.scroll(up=up, count=count)

    def click(self, button: str = "left") -> None:
        """Click the specified mouse button at the current position."""
        self._click_button(button)

    def move_to(
        self,
        x: int,
        y: int,
        within_ms: int | None = None,
        linear: bool = False,
    ) -> None:
        """Move the mouse cursor to the given window-relative coordinates."""
        self._move_to(x, y, within_ms=within_ms, linear=linear)

    def teleport(self, x: int, y: int) -> None:
        """Instantly move the cursor to window-relative coordinates, no path planning."""
        self._prepare()
        if self.cache:
            cx, cy = self.cache.canvas_offset
            x += cx
            y += cy
        self._a.teleport(float(x), float(y))

    def left_click(
        self,
        x: int | None = None,
        y: int | None = None,
        within_ms: int | None = None,
    ) -> None:
        """Left-click, optionally moving to (x, y) first."""
        if x is not None and y is not None:
            self._move_to(x, y, within_ms=within_ms)
        self._click_button("left")

    def right_click(
        self,
        x: int | None = None,
        y: int | None = None,
        within_ms: int | None = None,
    ) -> None:
        """Right-click, optionally moving to (x, y) first."""
        if x is not None and y is not None:
            self._move_to(x, y, within_ms=within_ms)

        self._click_button("right")

    def hold_left(
        self,
        x: int | None = None,
        y: int | None = None,
        within_ms: int | None = None,
    ) -> None:
        """Press and hold the left mouse button."""
        if x is not None and y is not None:
            self._move_to(x, y, within_ms=within_ms)

        self._hold("left")

    def hold_right(
        self,
        x: int | None = None,
        y: int | None = None,
        within_ms: int | None = None,
    ) -> None:
        """Press and hold the right mouse button."""
        if x is not None and y is not None:
            self._move_to(x, y, within_ms=within_ms)

        self._hold("right")

    def release_left(self) -> None:
        """Release the left mouse button."""
        self._release("left")

    def release_right(self) -> None:
        """Release the right mouse button."""
        self._release("right")

    def hold_middle(
        self,
        x: int | None = None,
        y: int | None = None,
        within_ms: int | None = None,
    ) -> None:
        """Press and hold the middle mouse button."""
        if x is not None and y is not None:
            self._move_to(x, y, within_ms=within_ms)
        self._hold("middle")

    def release_middle(self) -> None:
        """Release the middle mouse button."""
        self._release("middle")

    def click_at(self, x: int, y: int, button: str = "left") -> None:
        """Move to (x, y) and click the specified button."""
        self.move_to(x, y)
        if button == "left":
            self.left_click()
        elif button == "right":
            self.right_click()

    def scroll(self, up: bool = True, count: int = 1) -> None:
        """Scroll the mouse wheel up or down by the given number of clicks."""
        direction = 1 if up else -1

        for i in range(count):
            self._scroll(direction)

            if i < count - 1:
                time.sleep(random.uniform(0.025, 0.05))

    def click_polygon(
        self,
        polygon: Callable[[], Polygon],
        button: str = "left",
        within_ms: int | None = None,
        update_rate_hz: float = 10.0,
    ) -> None:
        """Move into the polygon region and click."""
        self._prepare()
        self._a.move_to(
            polygon=self._make_offset_polygon(polygon),
            within_ms=within_ms,
            update_rate_hz=update_rate_hz,
        )
        time.sleep(0.03)
        self._click_button(button)

    def hover_polygon(
        self,
        polygon: Callable[[], Polygon],
        within_ms: int | None = None,
        update_rate_hz: float = 100.0,
    ) -> None:
        """Move the cursor into the polygon region without clicking."""
        self._prepare()
        self._a.move_to(
            polygon=self._make_offset_polygon(polygon),
            within_ms=within_ms,
            update_rate_hz=update_rate_hz,
        )

    def enable_idle(self) -> None:
        """Enable idle mouse movement."""
        if self._agent:
            self._agent.idle_enabled = True

    def disable_idle(self) -> None:
        """Disable idle mouse movement."""
        if self._agent:
            self._agent.idle_enabled = False

    def is_idle_enabled(self) -> bool:
        """Return whether idle mouse movement is enabled."""
        return self._agent.idle_enabled if self._agent else False

    def stop(self) -> None:
        if self._agent is not None and self._agent_started:
            self._agent.stop()
            self._agent_started = False

    def __del__(self) -> None:
        if hasattr(self, "_agent") and self._agent is not None and self._agent_started:
            with contextlib.suppress(Exception):
                self._agent.stop()


# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------


def _build_char_map() -> dict[str, tuple[int, bool]]:
    m: dict[str, tuple[int, bool]] = {}

    for c in "abcdefghijklmnopqrstuvwxyz":
        keycode = getattr(e, f"KEY_{c.upper()}")
        m[c] = (keycode, False)
        m[c.upper()] = (keycode, True)

    num_row = "1234567890"
    shift_row = "!@#$%^&*()"
    for n, s in zip(num_row, shift_row, strict=False):
        keycode = getattr(e, f"KEY_{n}")
        m[n] = (keycode, False)
        m[s] = (keycode, True)

    m[" "] = (e.KEY_SPACE, False)
    m["\n"] = (e.KEY_ENTER, False)
    m["\t"] = (e.KEY_TAB, False)
    m["-"] = (e.KEY_MINUS, False)
    m["_"] = (e.KEY_MINUS, True)
    m["="] = (e.KEY_EQUAL, False)
    m["+"] = (e.KEY_EQUAL, True)
    m["["] = (e.KEY_LEFTBRACE, False)
    m["{"] = (e.KEY_LEFTBRACE, True)
    m["]"] = (e.KEY_RIGHTBRACE, False)
    m["}"] = (e.KEY_RIGHTBRACE, True)
    m["\\"] = (e.KEY_BACKSLASH, False)
    m["|"] = (e.KEY_BACKSLASH, True)
    m[";"] = (e.KEY_SEMICOLON, False)
    m[":"] = (e.KEY_SEMICOLON, True)
    m["'"] = (e.KEY_APOSTROPHE, False)
    m['"'] = (e.KEY_APOSTROPHE, True)
    m[","] = (e.KEY_COMMA, False)
    m["<"] = (e.KEY_COMMA, True)
    m["."] = (e.KEY_DOT, False)
    m[">"] = (e.KEY_DOT, True)
    m["/"] = (e.KEY_SLASH, False)
    m["?"] = (e.KEY_SLASH, True)
    m["`"] = (e.KEY_GRAVE, False)
    m["~"] = (e.KEY_GRAVE, True)

    return m


def _build_key_name_map() -> dict[str, int]:
    m: dict[str, int] = {}

    for c in "abcdefghijklmnopqrstuvwxyz":
        m[c] = getattr(e, f"KEY_{c.upper()}")
        m[c.upper()] = getattr(e, f"KEY_{c.upper()}")

    for n in range(10):
        m[str(n)] = getattr(e, f"KEY_{n}")

    for n in range(1, 13):
        m[f"f{n}"] = getattr(e, f"KEY_F{n}")

    m["up"] = e.KEY_UP
    m["down"] = e.KEY_DOWN
    m["left"] = e.KEY_LEFT
    m["right"] = e.KEY_RIGHT
    m["home"] = e.KEY_HOME
    m["end"] = e.KEY_END
    m["pageup"] = e.KEY_PAGEUP
    m["pagedown"] = e.KEY_PAGEDOWN

    m["backspace"] = e.KEY_BACKSPACE
    m["delete"] = e.KEY_DELETE
    m["insert"] = e.KEY_INSERT
    m["tab"] = e.KEY_TAB
    m["enter"] = e.KEY_ENTER
    m["return"] = e.KEY_ENTER

    m["space"] = e.KEY_SPACE
    m["escape"] = e.KEY_ESC
    m["esc"] = e.KEY_ESC
    m["capslock"] = e.KEY_CAPSLOCK
    m["numlock"] = e.KEY_NUMLOCK
    m["scrolllock"] = e.KEY_SCROLLLOCK
    m["printscreen"] = e.KEY_SYSRQ
    m["pause"] = e.KEY_PAUSE

    m["shift"] = e.KEY_LEFTSHIFT
    m["shiftleft"] = e.KEY_LEFTSHIFT
    m["shiftright"] = e.KEY_RIGHTSHIFT
    m["ctrl"] = e.KEY_LEFTCTRL
    m["ctrlleft"] = e.KEY_LEFTCTRL
    m["ctrlright"] = e.KEY_RIGHTCTRL
    m["alt"] = e.KEY_LEFTALT
    m["altleft"] = e.KEY_LEFTALT
    m["altright"] = e.KEY_RIGHTALT
    m["win"] = e.KEY_LEFTMETA
    m["winleft"] = e.KEY_LEFTMETA
    m["winright"] = e.KEY_RIGHTMETA

    for n in range(10):
        m[f"num{n}"] = getattr(e, f"KEY_KP{n}")
    m["divide"] = e.KEY_KPSLASH
    m["multiply"] = e.KEY_KPASTERISK
    m["subtract"] = e.KEY_KPMINUS
    m["add"] = e.KEY_KPPLUS
    m["decimal"] = e.KEY_KPDOT
    m["numpadenter"] = e.KEY_KPENTER

    return m


_CHAR_MAP = _build_char_map()
_KEY_NAME_MAP = _build_key_name_map()


class Keyboard:
    """Keyboard controller with human-like typing."""

    def __init__(self, runelite: RuneLite, speed: float = 1.0):
        self.runelite = runelite
        self.speed = speed
        self._keyboard: UInput | None = None

    def _ensure_keyboard(self) -> None:
        if self._keyboard is not None:
            return

        keys = [c for c in e.keys if isinstance(c, int)]
        self._keyboard = UInput(
            {e.EV_KEY: keys},  # type: ignore[arg-type]
            name="escape-keyboard",
        )

    @property
    def _k(self) -> UInput:
        assert self._keyboard is not None, "Keyboard device not initialized"
        return self._keyboard

    def _ensure_focus(self) -> None:
        self.runelite.refresh_window_position()

    def _press(self, key: str) -> None:
        self._ensure_keyboard()
        self._ensure_focus()

        keycode = _KEY_NAME_MAP.get(key.lower())
        if keycode is None:
            raise ValueError(f"Unknown key: {key}")

        self._k.write(e.EV_KEY, keycode, 1)
        self._k.syn()
        time.sleep(random.uniform(0.03, 0.07))
        self._k.write(e.EV_KEY, keycode, 0)
        self._k.syn()

    def _key_down(self, key: str) -> None:
        self._ensure_keyboard()
        self._ensure_focus()

        keycode = _KEY_NAME_MAP.get(key.lower())
        if keycode is None:
            raise ValueError(f"Unknown key: {key}")

        self._k.write(e.EV_KEY, keycode, 1)
        self._k.syn()

    def _key_up(self, key: str) -> None:
        self._ensure_keyboard()
        self._ensure_focus()

        keycode = _KEY_NAME_MAP.get(key.lower())
        if keycode is None:
            raise ValueError(f"Unknown key: {key}")

        self._k.write(e.EV_KEY, keycode, 0)
        self._k.syn()

    def type(self, text: str, humanize: bool = True) -> None:
        """Type a string of text with human-like delays."""
        if not text:
            return

        self._ensure_keyboard()
        self._ensure_focus()

        base_delay = 0.05 / self.speed

        for char in text:
            if char not in _CHAR_MAP:
                continue

            keycode, needs_shift = _CHAR_MAP[char]

            if needs_shift:
                self._k.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
                self._k.syn()

            self._k.write(e.EV_KEY, keycode, 1)
            self._k.syn()
            time.sleep(random.uniform(0.02, 0.05))

            self._k.write(e.EV_KEY, keycode, 0)
            self._k.syn()

            if needs_shift:
                self._k.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
                self._k.syn()

            if humanize:
                delay = base_delay * random.uniform(0.6, 1.4)

                if random.random() < 0.05:
                    delay += random.uniform(0.1, 0.3)

                time.sleep(delay)

    def press(self, key: str) -> None:
        """Press and release a single key."""
        self._press(key)
        time.sleep(random.uniform(0.02, 0.05))

    def hold(self, key: str) -> None:
        """Press and hold a key without releasing."""
        self._key_down(key)

    def release(self, key: str) -> None:
        """Release a held key."""
        self._key_up(key)
        time.sleep(random.uniform(0.02, 0.05))

    def hotkey(self, *keys: str) -> None:
        """Press a key combination (e.g. ctrl+a) and release in reverse order."""
        self._ensure_keyboard()
        self._ensure_focus()

        keycodes = []
        for key in keys:
            keycode = _KEY_NAME_MAP.get(key.lower())
            if keycode is None:
                raise ValueError(f"Unknown key: {key}")
            keycodes.append(keycode)

        for keycode in keycodes:
            self._k.write(e.EV_KEY, keycode, 1)
            self._k.syn()
            time.sleep(random.uniform(0.01, 0.03))

        for keycode in reversed(keycodes):
            self._k.write(e.EV_KEY, keycode, 0)
            self._k.syn()
            time.sleep(random.uniform(0.01, 0.03))

        time.sleep(random.uniform(0.03, 0.08))

    def press_enter(self) -> None:
        """Press the Enter key."""
        self.press("enter")

    def press_escape(self) -> None:
        """Press the Escape key."""
        self.press("escape")

    def press_space(self) -> None:
        """Press the Space key."""
        self.press("space")

    def press_tab(self) -> None:
        """Press the Tab key."""
        self.press("tab")

    def press_f_key(self, num: int) -> None:
        """Press a function key (F1-F12)."""
        if not 1 <= num <= 12:
            raise ValueError(f"Function key must be between 1 and 12, got {num}")

        self.press(f"f{num}")

    def press_number(self, num: int) -> None:
        """Press a number key (0-9)."""
        if not 0 <= num <= 9:
            raise ValueError(f"Number must be between 0 and 9, got {num}")

        self.press(str(num))

    def __del__(self) -> None:
        if hasattr(self, "_keyboard") and self._keyboard is not None:
            with contextlib.suppress(Exception):
                self._keyboard.close()
