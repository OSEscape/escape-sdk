"""Cache for storing varc (client variable) values."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape._proto.bridge.v1.bridge_pb2 import (  # pyright: ignore[reportMissingImports]
        VarcIntChanged,
        VarcIntSnapshot,
        VarcStrChanged,
        VarcStrSnapshot,
    )


class VarcCache:
    """Cache for varc (client variable) values."""

    def __init__(self):
        self.int_values: dict[int, int] = {}
        self.str_values: dict[int, str] = {}

    def set_varc_int(self, varc_id: int, value: int) -> None:
        """Set an integer varc value."""
        self.int_values[varc_id] = value

    def set_varc_str(self, varc_id: int, value: str) -> None:
        """Set a string varc value."""
        self.str_values[varc_id] = value

    def get_varc(self, varc_id: int) -> int | str | None:
        """Get a varc value (int or str)."""
        if varc_id in self.int_values:
            return self.int_values[varc_id]
        return self.str_values.get(varc_id)

    def process_snapshot_int(self, snapshot: VarcIntSnapshot) -> None:
        """Process integer varc snapshot."""
        for varc in snapshot.varcs:
            self.set_varc_int(varc.varc_id, varc.value)

    def process_snapshot_str(self, snapshot: VarcStrSnapshot) -> None:
        """Process string varc snapshot."""
        for varc in snapshot.varcs:
            self.set_varc_str(varc.varc_id, varc.value)

    def process_change_int(self, change: VarcIntChanged) -> None:
        """Process single integer varc change."""
        varc = change.varc_int_changed
        self.set_varc_int(varc.varc_id, varc.value)

    def process_change_str(self, change: VarcStrChanged) -> None:
        """Process single string varc change."""
        varc = change.varc_str_changed
        self.set_varc_str(varc.varc_id, varc.value)
