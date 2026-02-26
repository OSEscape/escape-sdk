import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import py_trees

from escape._logger import logger
from escape.bt.actions import Status
from escape.bt.context import Blackboard

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class NodeStats:
    success_count: int = 0
    failure_count: int = 0
    running_count: int = 0


class StatsVisitor(py_trees.visitors.VisitorBase):
    def __init__(self) -> None:
        super().__init__(full=True)
        self._stats: dict[str, NodeStats] = {}
        self._last_status: dict[str, Status] = {}

    def run(self, behaviour: py_trees.behaviour.Behaviour) -> None:
        name = behaviour.name
        status = behaviour.status
        if name not in self._stats:
            self._stats[name] = NodeStats()
        last = self._last_status.get(name)
        if status != last:
            stats = self._stats[name]
            if status == Status.SUCCESS:
                stats.success_count += 1
            elif status == Status.FAILURE:
                stats.failure_count += 1
            elif status == Status.RUNNING:
                stats.running_count += 1
            self._last_status[name] = status

    def get(self, node_name: str) -> NodeStats | None:
        return self._stats.get(node_name)

    def summary(self) -> str:
        lines = ["Node Statistics:", "-" * 50]
        for name, stats in sorted(self._stats.items()):
            parts = []
            if stats.success_count:
                parts.append(f"S:{stats.success_count}")
            if stats.failure_count:
                parts.append(f"F:{stats.failure_count}")
            if stats.running_count:
                parts.append(f"R:{stats.running_count}")
            if parts:
                lines.append(f"  {name}: {' '.join(parts)}")
        return "\n".join(lines)

    def reset(self) -> None:
        self._stats.clear()
        self._last_status.clear()


class BehaviorTreeRunner:
    def __init__(
        self,
        tree: py_trees.behaviour.Behaviour,
        blackboard: Blackboard | None = None,
        tick_rate: float = 0.05,
        on_tick: Callable[[Status, int], None] | None = None,
        collect_stats: bool = False,
    ) -> None:
        self._bt = py_trees.trees.BehaviourTree(root=tree)
        self.blackboard = blackboard or Blackboard()
        self.tick_rate = tick_rate
        self.on_tick = on_tick
        self._setup_done = False
        self.stats: StatsVisitor | None = None
        if collect_stats:
            self.stats = StatsVisitor()
            self._bt.add_visitor(self.stats)

    def _ensure_setup(self) -> None:
        if self._setup_done:
            return
        self._bt.setup(blackboard=self.blackboard)
        self._setup_done = True

    def tick(self) -> Status:
        self._ensure_setup()
        try:
            self._bt.tick()
        except Exception:
            logger.exception("Exception during tree tick")
            self._bt.root.stop(Status.INVALID)
            return Status.FAILURE
        status = self._bt.root.status
        if self.on_tick:
            self.on_tick(status, self._bt.count)
        return status

    @property
    def tick_count(self) -> int:
        return self._bt.count

    def run(self, max_ticks: int | None = None) -> Status:
        ticks = 0
        while max_ticks is None or ticks < max_ticks:
            status = self.tick()
            if status != Status.RUNNING:
                return status
            ticks += 1
            time.sleep(self.tick_rate)
        return Status.RUNNING

    def reset(self) -> None:
        if self._setup_done:
            self._bt.root.stop(Status.INVALID)
        self._bt.count = 0
        self._setup_done = False
        if self.stats:
            self.stats.reset()

    def find_failure(self) -> str | None:
        """Walk the tree and return the name of the leaf node that caused FAILURE.

        For Selectors the last failing child is the meaningful one (earlier
        children are expected to fail). For Sequences the first failing child
        is the one that broke the chain.
        """
        node = self._bt.root
        while node.status == Status.FAILURE:
            if not node.children:
                return node.name
            failed = [c for c in node.children if c.status == Status.FAILURE]
            if not failed:
                return node.name
            # Selector: last child is the meaningful failure
            # Sequence: first child is the meaningful failure
            is_selector = isinstance(node, py_trees.composites.Selector)
            node = failed[-1] if is_selector else failed[0]
        return None

    def visualize(self, show_status: bool = True) -> str:
        return py_trees.display.ascii_tree(self._bt.root, show_status=show_status)

    def visualize_unicode(self, show_status: bool = True) -> str:
        return py_trees.display.unicode_tree(self._bt.root, show_status=show_status)
