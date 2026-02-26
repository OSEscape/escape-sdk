"""Transport layer for gRPC communication."""

import asyncio
import os

import grpc
from bridge.v1 import bridge_pb2_grpc  # pyright: ignore[reportMissingImports]

__all__ = ["DIRECT_METADATA", "AsyncTransport", "Transport"]

SOCKET_PATH = os.environ.get("BRIDGE_SOCKET") or f"{os.environ['XDG_RUNTIME_DIR']}/bridge.sock"
DIRECT_METADATA: list[tuple[str, str]] = [("direct-execution", "true")]


class Transport:
    """Synchronous gRPC transport manager."""

    _instance = None

    def __new__(cls, socket_path: str | None = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init(socket_path)
        return cls._instance

    def _init(self, socket_path: str | None = None) -> None:
        path = socket_path or SOCKET_PATH
        self._channel = grpc.insecure_channel(f"unix://{path}")
        self._stub = bridge_pb2_grpc.BridgeServiceStub(self._channel)

    @property
    def stub(self) -> bridge_pb2_grpc.BridgeServiceStub:
        return self._stub

    def close(self) -> None:
        """Close the synchronous gRPC channel."""
        self._channel.close()


class AsyncTransport:
    """Asynchronous gRPC transport manager powered by asyncio."""

    _instance = None
    _loop: asyncio.AbstractEventLoop | None = None

    def __new__(cls, socket_path: str | None = None):
        loop = asyncio.get_running_loop()
        if cls._instance is None or cls._loop is not loop:
            cls._instance = super().__new__(cls)
            cls._instance._init(socket_path)
            cls._loop = loop
        return cls._instance

    def _init(self, socket_path: str | None = None) -> None:
        path = socket_path or SOCKET_PATH
        self._channel = grpc.aio.insecure_channel(f"unix://{path}")
        self._stub = bridge_pb2_grpc.BridgeServiceStub(self._channel)

    @property
    def stub(self) -> bridge_pb2_grpc.BridgeServiceStub:
        return self._stub

    async def close(self) -> None:
        """Asynchronously close the gRPC channel."""
        await self._channel.close()
