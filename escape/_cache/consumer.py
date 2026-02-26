"""Event consumer module.

Streams real-time updates from the Java Bridge, feeds them to the ProcessedCache,
and broadcasts high-level signals via the EventBus. Runs async internally on a
dedicated daemon thread; all public methods are synchronous.
"""

import asyncio
import threading
from typing import TYPE_CHECKING

from escape._logger import logger
from escape._proto.bridge.v1 import bridge_pb2 as pb
from escape._transport import AsyncTransport

if TYPE_CHECKING:
    from escape._cache.processed_cache import ProcessedCache


class EventConsumer:
    """Background event consumer for the gRPC stream.

    Runs an asyncio event loop on a daemon thread. The stream stays async
    internally (gRPC streaming requires it), but the public API is sync.
    """

    def __init__(self):
        self._cache: ProcessedCache | None = None
        self._running = False
        self._connected = False
        self._warmup_complete = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._task: asyncio.Task | None = None
        self._call = None

    def start(self, cache: ProcessedCache, wait_for_warmup: bool = False):
        """Launch the background consumption loop on a daemon thread."""
        self._cache = cache
        if self._running:
            logger.warning("EventConsumer is already active.")
            return

        self._running = True

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._task = self._loop.create_task(self._consume_loop())
                self._loop.run_until_complete(self._task)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"EventConsumer loop crashed: {e}")
            finally:
                self._loop.run_until_complete(self._drain_pending())
                self._loop.close()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        logger.info("EventConsumer background thread started.")

        if wait_for_warmup:
            logger.info("Awaiting initial state snapshots (warmup)...")
            if self._warmup_complete.wait(timeout=10.0):
                logger.info("Warmup finalized; cache fully populated.")
            else:
                logger.warning("Warmup timed out; cache may be in an incomplete state.")

    def stop(self):
        """Shut down the background thread and close the gRPC connection."""
        if not self._running:
            return

        logger.info("Deactivating EventConsumer...")
        self._running = False
        if self._loop:
            if self._call:
                self._loop.call_soon_threadsafe(self._call.cancel)
            if self._task:
                self._loop.call_soon_threadsafe(self._task.cancel)
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._task = None
        self._call = None
        self._loop = None
        logger.info("EventConsumer stopped.")

    async def _drain_pending(self):
        current = asyncio.current_task()
        pending = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def _request_generator(self):
        options = pb.SubscriptionOptions(enable_all=True)
        yield pb.ClientMessage(subscribe=pb.Subscribe(options=options))

        while self._running:
            await asyncio.sleep(1)

    async def _consume_loop(self):
        logger.debug("Starting EventConsumer core loop.")
        assert self._cache is not None
        cache = self._cache
        retry_delay = 1.0
        max_retry_delay = 30.0

        transport = AsyncTransport()

        while self._running:
            try:
                logger.info("Establishing gRPC event stream...")
                self._call = transport.stub.Subscribe(self._request_generator())  # pyright: ignore[reportArgumentType]
                self._connected = True
                logger.info("Event stream connected.")
                retry_delay = 1.0

                async for msg in self._call:  # pyright: ignore[reportGeneralTypeIssues]
                    if not self._running:
                        break

                    # grpc silently returns None when deserialization fails
                    # (see grpc._common._transform) — skip corrupted frames
                    if msg is None:
                        logger.warning("Received None from gRPC stream (deserialization failure)")
                        continue

                    field_name = msg.WhichOneof("message")
                    if not field_name:
                        continue

                    event = getattr(msg, field_name)

                    try:
                        cache.process_event(field_name, event)

                        if field_name == "warmup_complete" and not self._warmup_complete.is_set():
                            self._warmup_complete.set()

                    except Exception as e:
                        logger.error(f"Failed to process event '{field_name}': {e}")

            except Exception as e:
                self._connected = False
                # Clear entity subscriptions so next access re-subscribes
                cache.clear_entity_subscriptions()
                if self._running:
                    logger.error(f"Event stream encountered an error: {e}")
                    logger.info(f"Retrying connection in {retry_delay:.1f}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_retry_delay)
            finally:
                if self._call is not None:
                    self._call.cancel()
                    self._call = None

        logger.info("EventConsumer loop terminated.")
