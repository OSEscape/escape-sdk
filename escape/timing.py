import random
import time
from typing import TYPE_CHECKING

from escape._logger import logger
from escape.events import TickEvent

if TYPE_CHECKING:
    from collections.abc import Callable


def wait_ticks(ticks: int, timeout: float | None = None):
    if ticks <= 0:
        return

    from escape._services import Services

    cache = Services.get().cache
    start_tick = cache.tick or 0
    remaining = ticks
    deadline = time.time() + timeout if timeout is not None else None

    while remaining > 0:
        per_tick_timeout = (deadline - time.time()) if deadline is not None else None
        if per_tick_timeout is not None and per_tick_timeout <= 0:
            return
        cache.events.wait_for(TickEvent, timeout=per_tick_timeout)
        current = cache.tick or 0
        remaining = ticks - (current - start_tick)


def sleep(min_seconds: float, max_seconds: float | None = None):
    if max_seconds is None:
        time.sleep(min_seconds)
    else:
        duration = random.uniform(min_seconds, max_seconds)
        time.sleep(duration)


def wait_until(
    condition: Callable[[], bool],
    timeout: float = 10.0,
    poll_interval: float = 0.05,
) -> bool:
    if condition():
        return True

    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        time.sleep(poll_interval)

    return False


def wait_until_ticks(condition: Callable[[], bool], ticks: int) -> bool:
    """Poll *condition* once per game tick for up to *ticks* ticks."""
    if condition():
        return True

    from escape._services import Services

    cache = Services.get().cache
    start_tick = cache.tick or 0

    while (cache.tick or 0) - start_tick < ticks:
        cache.events.wait_for(TickEvent, timeout=5.0)
        if condition():
            return True

    return False


def retry(
    func: Callable,
    max_attempts: int = 3,
    delay: float = 1.0,
    exponential_backoff: bool = False,
):
    current_delay = delay

    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                logger.error(f"All {max_attempts} attempts failed: {e}")
                return None

            logger.error(f"Attempt {attempt + 1} failed: {e}. Retrying in {current_delay}s")
            time.sleep(current_delay)

            if exponential_backoff:
                current_delay *= 2

    return None
