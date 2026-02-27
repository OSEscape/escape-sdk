"""Cache for storing chat message history."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape._proto.bridge.v1.bridge_pb2 import (  # pyright: ignore[reportMissingImports]
        ChatChanged,
        ChatSnapshot,
    )


@dataclass(frozen=True)
class ChatMessage:
    """Represents a chat message."""

    type: str
    sender: str
    message: str
    timestamp: float


class ChatCache:
    """Cache for chat message history."""

    def __init__(self, maxlen: int = 100):
        self.messages: deque[ChatMessage] = deque(maxlen=maxlen)

    def add_message(self, msg_type: str, sender: str, message: str) -> None:
        """Add a chat message."""
        self.messages.append(ChatMessage(msg_type, sender, message, time.time()))

    def process_snapshot(self, snapshot: ChatSnapshot) -> None:
        """Process chat snapshot - load initial messages."""
        for msg in snapshot.messages:
            self.add_message(msg.type, msg.sender, msg.message)

    def process_change(self, change: ChatChanged) -> None:
        """Process single chat message."""
        msg = change.message
        self.add_message(msg.type, msg.sender, msg.message)

    def get_recent(self, n: int | None = None) -> list[ChatMessage]:
        """Get recent messages. If n is None, return all."""
        if n is None:
            return list(self.messages)
        return list(self.messages)[-n:]
