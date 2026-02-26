from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape.navigation.solver import TransportSolver
    from escape.pathfinder import Transport
    from escape.pathfinding.core.enums import TransportType


class SolverRegistry:
    """Registry that maps transports to solvers.

    Name-based exceptions are checked first, then type-based defaults.
    """

    def __init__(self) -> None:
        self._by_type: dict[TransportType, TransportSolver] = {}
        self._by_name: dict[str, TransportSolver] = {}

    def register(self, *types: TransportType, solver: TransportSolver) -> None:
        """Register a solver as the default for one or more transport types."""
        for t in types:
            self._by_type[t] = solver

    def exception(self, name: str, solver: TransportSolver) -> None:
        """Override the solver for a specific transport by name."""
        self._by_name[name] = solver

    def resolve(self, transport: Transport) -> TransportSolver | None:
        """Resolve the solver for a transport.

        Name match takes priority over type match.
        """
        solver = self._by_name.get(transport.name)
        if solver is not None:
            return solver
        return self._by_type.get(transport.transport_type)


def default_registry() -> SolverRegistry:
    """Create a registry with sensible defaults for common transport types."""
    from escape.navigation.solvers.charter_ship import CharterShipSolver
    from escape.navigation.solvers.fairy_ring import FairyRingSolver
    from escape.navigation.solvers.item_teleport import ItemTeleportSolver
    from escape.navigation.solvers.npc_click import NpcClickSolver
    from escape.navigation.solvers.object_click import TransportClickSolver
    from escape.navigation.solvers.spell_teleport import SpellTeleportSolver
    from escape.pathfinding.core.enums import TransportType

    registry = SolverRegistry()
    click = TransportClickSolver()
    registry.register(
        TransportType.TRANSPORT,
        TransportType.AGILITY_SHORTCUT,
        TransportType.TELEPORTATION_LEVER,
        TransportType.TELEPORTATION_PORTAL,
        solver=click,
    )
    npc_click = NpcClickSolver()
    registry.register(
        TransportType.BOAT,
        TransportType.SHIP,
        solver=npc_click,
    )
    registry.register(
        TransportType.TELEPORTATION_SPELL,
        solver=SpellTeleportSolver(),
    )
    registry.register(
        TransportType.TELEPORTATION_ITEM,
        solver=ItemTeleportSolver(),
    )
    registry.register(
        TransportType.FAIRY_RING,
        solver=FairyRingSolver(),
    )
    registry.register(
        TransportType.CHARTER_SHIP,
        solver=CharterShipSolver(),
    )
    return registry
