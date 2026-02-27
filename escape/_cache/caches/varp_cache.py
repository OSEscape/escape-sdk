"""Cache for storing varp (server variable) values."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape._proto.bridge.v1.bridge_pb2 import (  # pyright: ignore[reportMissingImports]
        VarbitChanged,
        VarpSnapshot,
    )


class VarpCache:
    """Cache for varp (server variable) values."""

    def __init__(self):
        self.values: dict[int, int] = {}

    def set_varp(self, varp_id: int, value: int) -> None:
        """Set a varp value."""
        self.values[varp_id] = value

    def get_varp(self, varp_id: int) -> int:
        """Get a varp value."""
        return self.values.get(varp_id, 0)

    def process_snapshot(self, snapshot: VarpSnapshot) -> None:
        """Process varp snapshot - build full array from initial state."""
        for varp in snapshot.varps:
            # Both varps and varbits set the parent varp value
            self.set_varp(varp.varp_id, varp.value)

    def process_change(self, change: VarbitChanged) -> None:
        """Process single varbit/varp change."""
        varp = change.varbit_changed
        varbit_id = varp.varbit_id

        if varbit_id == -1:
            # Pure varp change — value is the full 32-bit varp
            self.set_varp(varp.varp_id, varp.value)
        else:
            # Varbit change — value is the extracted varbit, splice it into the varp
            from escape._resources import varps as varps_mod

            info = varps_mod.get_varbit_info(varbit_id)
            if info is None:
                return
            lsb = info["lsb"]
            msb = info["msb"]
            num_bits = msb - lsb + 1
            mask = (1 << num_bits) - 1
            current = self.values.get(varp.varp_id, 0)
            current &= ~(mask << lsb)  # clear the varbit's bits
            current |= (varp.value & mask) << lsb  # set new value
            self.set_varp(varp.varp_id, current)
