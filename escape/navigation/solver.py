from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from escape.bt.actions import Status
    from escape.pathfinder import Transport


@runtime_checkable
class TransportSolver(Protocol):
    """Protocol for transport solvers.

    Called each tick while a transport is being solved.
    Return RUNNING while in progress, SUCCESS when done, FAILURE to give up.
    """

    def solve(self, transport: Transport) -> Status:
        """Tick the solver. Return RUNNING/SUCCESS/FAILURE."""
        ...

    def reset(self) -> None:
        """Reset internal state for a new transport."""
        ...
