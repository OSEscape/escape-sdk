"""Login automation — navigates login screens and enters credentials."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from google.protobuf.empty_pb2 import Empty

from escape._logger import logger
from escape._services import Services
from escape.constants import InterfaceID
from escape.geometry import Box
from escape.timing import sleep, wait_until
from escape.widget import Buttons

CREDENTIALS_PATH = Path.home() / "alpine" / "credentials" / "credentials.json"

# 20x20 boxes centred on each button
_EULA_ACCEPT = Box(292, 304, 20, 20)  # login_index 12
_EXISTING_USER = Box(452, 280, 20, 20)  # login_index 0
_LOGIN_BUTTON = Box(294, 313, 20, 20)  # login_index 2
_LAUNCHER_PLAY = Box(370, 255, 20, 20)  # login_index 9, 10
_OK_BUTTON = Box(358, 285, 20, 20)  # login_index 3, 24


def _welcome_open() -> bool:
    s = Services.get()
    return InterfaceID.WELCOME_SCREEN in s.cache.active_interfaces


def _dismiss_welcome_screen() -> bool:
    """Wait for the welcome screen and click Play."""
    s = Services.get()
    play_button = Buttons(
        InterfaceID.WELCOME_SCREEN,
        [InterfaceID.WelcomeScreen.PLAY],
        ["Play"],
        can_move=True,
        menu_text="Play",
    )

    if play_button.interact("Play"):
        logger.info("Clicked Play on welcome screen")
        sleep(0.8, 1.2)
        return True

    return False


def is_logged_in() -> bool:
    """Returns True if the client is currently logged in."""
    s = Services.get()
    result = s.cache.game_state in ("LOGGED_IN", "LOADING") and not _welcome_open()
    if not result:
        logger.debug(
            f"Not logged in (game_state={s.cache.game_state}, welcome_open={_welcome_open()})"
        )
    return result


def login(timeout: float = 30.0) -> bool:
    """Navigate login screens, enter credentials, and dismiss the welcome screen.

    Returns True if the client reaches LOGGED_IN within *timeout* seconds.
    """
    if is_logged_in():
        logger.info("Already logged in")
        _dismiss_welcome_screen()
        return True

    creds = json.loads(CREDENTIALS_PATH.read_text())
    username = creds["username"]
    password = creds["password"]

    s = Services.get()

    if _welcome_open():
        _dismiss_welcome_screen()
        return True

    import time

    deadline = time.time() + timeout
    fail_count = 0

    while time.time() < deadline:
        state = s.cache.game_state
        logger.info(f"state={state}")

        if state == "LOGGED_IN":
            logger.info("Login complete")
            wait_until(lambda: _welcome_open(), timeout=5.0)
            _dismiss_welcome_screen()
            return True

        if state != "LOGIN_SCREEN":
            sleep(0.6)
            continue

        if state == "LOADING":
            logger.debug("Game is loading, waiting")
            wait_until(lambda: s.cache.game_state != "LOADING", timeout=15.0)
            continue

        login_index = s.stub.GetLoginIndex(Empty()).login_index
        logger.debug(f"login_index={login_index} game_state={state}")

        if login_index in (9, 12):
            # EULA screen — click accept
            _EULA_ACCEPT.interact()
            sleep(0.8, 1.2)

        elif login_index == 0:
            # Main screen — click "Existing User"
            _EXISTING_USER.interact()
            sleep(0.8, 1.2)

        elif login_index == 2:
            # Credentials screen — set credentials via RPC then click login
            from escape._proto.bridge.v1 import bridge_pb2  # pyright: ignore[reportMissingImports]

            s.stub.SetCredentials(
                bridge_pb2.SetCredentialsRequest(
                    username=username,
                    password=password,
                )
            )
            sleep(0.3, 0.5)
            _LOGIN_BUTTON.interact()
            sleep(1.0, 1.5)

        elif login_index == 10:
            # Jagex launcher / "try again" prompt — click through
            _LAUNCHER_PLAY.interact()
            sleep(0.8, 1.2)

        elif login_index in (3, 24):
            # Wrong credentials / disconnected — click OK then terminate
            _OK_BUTTON.interact()
            sleep(0.5)
            logger.error(
                f"Login failed (login_index={login_index}): wrong credentials or disconnected"
            )
            fail_count += 1
            if fail_count >= 3:
                sys.exit(1)

        elif login_index == 4:
            # OTP required — cannot proceed
            logger.error("Login failed: authenticator (OTP) required")
            sys.exit(1)

        elif login_index == 14:
            # Account banned
            logger.error("Login failed: account is banned")
            sys.exit(1)

        elif login_index == 34:
            # Members world on F2P account
            logger.error("Login failed: not a member, cannot log into members world")
            sys.exit(1)

        else:
            logger.debug(f"Unhandled login_index={login_index}, waiting")
            sleep(0.6)

    logger.warning("Login timed out")
    return False
