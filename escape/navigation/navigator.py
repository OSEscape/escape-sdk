from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from escape._logger import logger
from escape.bt.actions import Status
from escape.navigation.walk import Walk
from escape.point import Point

if TYPE_CHECKING:
    from escape._cache.processed_cache import ProcessedCache
    from escape.navigation.registry import SolverRegistry
    from escape.navigation.solver import TransportSolver
    from escape.pathfinder import Path, Pathfinder, PathfinderConfig, Transport
    from escape.walker import Walker


@dataclass
class RouteStep:
    target: Point
    transport: Transport | None = None


class Navigator:
    """Framework-agnostic navigation engine.

    Computes a global route once, then walks each segment using fresh static BFS
    per tick, validated against live scene collision data.
    """

    def __init__(
        self,
        dest: Point,
        walker: Walker,
        pathfinder: Pathfinder,
        registry: SolverRegistry,
        config: PathfinderConfig | None = None,
        arrival_threshold: int = 2,
    ) -> None:
        self._dest = dest
        self._walker = walker
        self._pathfinder = pathfinder
        self._registry = registry
        self._config = config
        self._arrival_threshold = arrival_threshold

        self._route: list[RouteStep] = []
        self._route_idx: int = 0
        self._active_solver: TransportSolver | None = None
        self._active_transport: Transport | None = None
        self._block_count: int = 0
        self._walk: Walk | None = None
        self._early_start: bool = False
        self._early_click_failed: bool = False

    @property
    def _cache(self) -> ProcessedCache:
        from escape._services import Services

        return Services.get().cache

    def reset(self) -> None:
        self._route = []
        self._route_idx = 0
        self._active_solver = None
        self._active_transport = None
        self._block_count = 0
        self._walk = None
        self._early_start = False
        self._early_click_failed = False

    # ------------------------------------------------------------------
    # Main tick
    # ------------------------------------------------------------------

    def tick(self) -> Status:
        pos = self._cache.world_position
        logger.debug(
            "nav | pos={} dest={} route={}/{} solver={}",
            pos,
            self._dest,
            self._route_idx,
            len(self._route),
            self._active_transport.name if self._active_transport else None,
        )

        if self._is_near(self._dest):
            logger.debug("nav → arrived")
            return Status.SUCCESS

        # Active transport solver — keep ticking
        if self._active_solver is not None:
            return self._tick_solver()

        # Plan route once from global pathfinder
        if not self._route:
            result = self._plan_route()
            if result is not None:
                return result

        if self._route_idx >= len(self._route):
            logger.debug("nav → route exhausted but not arrived")
            return Status.FAILURE

        step = self._route[self._route_idx]

        # Transport step and near origin → start solver
        if step.transport is not None and self._is_near(step.transport.origin):
            return self._start_solver(step.transport)

        # Walk step with upcoming transport — try early click if origin is visible
        if step.transport is None and not self._early_click_failed:
            next_idx = self._route_idx + 1
            if next_idx < len(self._route):
                next_step = self._route[next_idx]
                if next_step.transport is not None:
                    origin = next_step.transport.origin
                    if self._walker._scene.is_tile_on_screen(origin.x, origin.y):
                        logger.debug("nav: early click — origin ({},{}) on screen", origin.x, origin.y)
                        self._early_start = True
                        return self._start_solver(next_step.transport)

        # Walk toward step target
        return self._tick_walk(step)

    # ------------------------------------------------------------------
    # Route planning
    # ------------------------------------------------------------------

    def _plan_route(self) -> Status | None:
        path = self._pathfinder.find_path(self._dest, config=self._config)
        if not path.found or path.is_empty():
            logger.debug("nav → no global path")
            return Status.FAILURE

        self._route = self._build_route(path)
        self._route_idx = 0
        logger.debug("nav: planned route with {} steps", len(self._route))
        for i, step in enumerate(self._route):
            if step.transport:
                logger.debug(
                    "  step[{}]: transport '{}' {} → {}",
                    i, step.transport.name, step.transport.origin, step.transport.destination,
                )
            else:
                logger.debug("  step[{}]: walk → {}", i, step.target)
        return None

    @staticmethod
    def _build_route(path: Path) -> list[RouteStep]:
        steps: list[RouteStep] = []
        if not path.transports:
            steps.append(RouteStep(target=path.tile_path[-1]))
            return steps

        for transport in path.transports:
            if transport.origin == transport.destination:
                continue
            steps.append(RouteStep(target=transport.origin))
            steps.append(RouteStep(target=transport.destination, transport=transport))

        # Walk to final destination after last transport
        steps.append(RouteStep(target=path.tile_path[-1]))
        return steps

    # ------------------------------------------------------------------
    # Transport solving
    # ------------------------------------------------------------------

    def _tick_solver(self) -> Status:
        result = self._active_solver.solve(self._active_transport)  # type: ignore[arg-type]
        if result == Status.RUNNING:
            return Status.RUNNING
        logger.debug(
            "nav: solver done ({}) for '{}'",
            result,
            self._active_transport.name if self._active_transport else "?",
        )
        was_early = self._early_start
        self._active_solver = None
        self._active_transport = None
        self._early_start = False
        if result == Status.SUCCESS:
            self._route_idx += 2 if was_early else 1
            self._early_click_failed = False
            self._walk = None
        elif was_early:
            self._early_click_failed = True
            logger.debug("nav: early click failed, resuming walk")
        return Status.RUNNING

    def _start_solver(self, transport: Transport) -> Status:
        solver = self._registry.resolve(transport)
        if solver is None:
            logger.debug("nav: no solver for '{}' (type={})", transport.name, transport.transport_type)
            if self._early_start:
                self._early_start = False
                self._early_click_failed = True
            return Status.FAILURE if not self._early_click_failed else Status.RUNNING
        solver.reset()
        self._active_solver = solver
        self._active_transport = transport
        result = solver.solve(transport)
        logger.debug("nav → solver started for '{}' → {}", transport.name, result)
        if result != Status.RUNNING:
            was_early = self._early_start
            self._active_solver = None
            self._active_transport = None
            self._early_start = False
            if result == Status.SUCCESS:
                self._route_idx += 2 if was_early else 1
                self._early_click_failed = False
                self._walk = None
            elif was_early:
                self._early_click_failed = True
                logger.debug("nav: early click failed immediately, resuming walk")
        return Status.RUNNING

    # ------------------------------------------------------------------
    # Walking (delegated to Walk)
    # ------------------------------------------------------------------

    def _tick_walk(self, step: RouteStep) -> Status:
        if self._is_near(step.target):
            logger.debug("nav: reached step target {}", step.target)
            self._route_idx += 1
            self._block_count = 0
            self._walk = None
            self._early_click_failed = False
            return Status.RUNNING

        if self._walk is None:
            self._walk = Walk(step.target, self._walker, self._pathfinder, self._arrival_threshold)

        result = self._walk.tick()
        if result == Status.FAILURE:
            return self._handle_blocked(self._walk.last_static_tiles)

        self._block_count = 0
        return result

    # ------------------------------------------------------------------
    # Obstacle handling
    # ------------------------------------------------------------------

    def _handle_blocked(self, static_tiles: list[tuple[int, int, int]]) -> Status:
        self._block_count += 1
        logger.debug("nav: blocked (count={})", self._block_count)

        if self._block_count < 3:
            return Status.RUNNING

        # Find the blocking object and try to interact
        if len(static_tiles) >= 2:
            blocked_wx, blocked_wy, _ = static_tiles[1]
            if self._interact_obstacle(blocked_wx, blocked_wy):
                self._block_count = 0
                return Status.RUNNING

        # Re-plan globally
        logger.debug("nav: obstacle unresolved → re-plan")
        self._route = []
        self._block_count = 0
        self._walk = None
        return Status.RUNNING

    def _interact_obstacle(self, world_x: int, world_y: int) -> bool:
        """Try to open/pass an obstacle near the given world tile."""
        from escape.objects import Objects

        objects = Objects()
        pos = self._cache.world_position
        if pos is None:
            return False
        _, _, plane = pos

        # Look for interactable objects near the blocked tile
        nearby = objects.get(max_distance=3, plane=plane)
        obstacle_actions = {"open", "close", "pass-through", "pass", "enter", "use"}

        best = None
        best_dist = 999
        for obj in nearby:
            obj_actions = {a.lower() for a in obj.actions}
            matching = obj_actions & obstacle_actions
            if matching and obj.distance < best_dist:
                best = obj
                best_dist = obj.distance

        if best is None:
            logger.debug("nav: no obstacle object found near ({}, {})", world_x, world_y)
            return False

        # Pick the first matching action
        action = None
        for a in best.actions:
            if a.lower() in obstacle_actions:
                action = a
                break

        logger.debug(
            "nav: interacting with obstacle '{}' action='{}' at ({},{})",
            best.name, action, best.world_x, best.world_y,
        )
        obj = objects.nearest(ids=[best.id], options=[action] if action else None, plane=plane)
        if obj is None:
            return False
        return obj.interact(action)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_near(self, point: Point) -> bool:
        pos = self._cache.world_position
        if pos is None:
            return False
        return point.is_nearby(Point(*pos), self._arrival_threshold)
