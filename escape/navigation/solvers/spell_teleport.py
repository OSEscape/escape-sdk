from __future__ import annotations

from typing import TYPE_CHECKING

from escape._logger import logger
from escape.bt.actions import Status
from escape.navigation.click import Click
from escape.navigation.solvers.spell_data import SPELLBOOK_VARBIT, lookup_spell
from escape.point import Point

if TYPE_CHECKING:
    from escape.pathfinder import Transport


class SpellTeleportSolver:
    """Transport solver: cast a teleport spell, wait for arrival."""

    def __init__(self) -> None:
        self._clicker: Click | None = None

    def reset(self) -> None:
        if self._clicker is not None:
            self._clicker.reset()
        self._clicker = None

    def solve(self, transport: Transport) -> Status:
        if self._clicker is None:
            spellbook = self._extract_spellbook(transport)
            spell = lookup_spell(transport.name, spellbook=spellbook)
            if spell is None:
                logger.warning(
                    "spell-solver: unknown spell '{}' (spellbook={})", transport.name, spellbook
                )
                return Status.FAILURE

            def cast() -> bool:
                from escape.magic import Magic

                magic = Magic()
                logger.debug(
                    "spell-solver: casting '{}' widget=0x{:08X} option='{}'",
                    transport.name,
                    spell.widget_id,
                    spell.option,
                )
                ok = magic.cast_spell(spell.widget_id, option=spell.option)
                logger.debug("spell-solver: cast '{}' → {}", transport.name, ok)
                return ok

            duration = transport.metadata[0].duration_ticks if transport.metadata else 0
            self._clicker = Click(
                click=cast,
                is_complete=lambda: self._near_destination(transport),
                timeout_ticks=3 + duration,
                name=f"spell-{transport.name}",
            )

        return self._clicker.tick()

    def _near_destination(self, transport: Transport) -> bool:
        from escape._services import Services

        cache = Services.get().cache
        pos = cache.world_position
        return pos is not None and transport.destination.is_nearby(Point(*pos), 5)

    @staticmethod
    def _extract_spellbook(transport: Transport) -> int | None:
        """Extract the spellbook varbit value from transport metadata."""
        if not transport.metadata:
            return None
        meta = transport.metadata[0]
        for varbit_id, value, _check in meta.varbit_requirements:
            if varbit_id == SPELLBOOK_VARBIT:
                return value
        return None
