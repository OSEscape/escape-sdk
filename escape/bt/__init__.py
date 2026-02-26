from typing import TYPE_CHECKING

import py_trees

from escape.bt.actions import (
    Action,
    Condition,
    ForEach,
    Status,
    action_node,
    condition_node,
)
from escape.bt.context import Blackboard
from escape.bt.runner import BehaviorTreeRunner, NodeStats, StatsVisitor

if TYPE_CHECKING:
    from collections.abc import Sequence as Seq


def Sequence(  # noqa: N802
    name: str = "Sequence",
    children: Seq[py_trees.behaviour.Behaviour] | None = None,
    *,
    memory: bool = True,
) -> py_trees.composites.Sequence:
    """Create a sequence composite node."""
    return py_trees.composites.Sequence(name=name, memory=memory, children=children)


def Selector(  # noqa: N802
    name: str = "Selector",
    children: Seq[py_trees.behaviour.Behaviour] | None = None,
    *,
    memory: bool = True,
) -> py_trees.composites.Selector:
    """Create a selector composite node."""
    return py_trees.composites.Selector(name=name, memory=memory, children=children)


def Parallel(  # noqa: N802
    name: str = "Parallel",
    children: Seq[py_trees.behaviour.Behaviour] | None = None,
    *,
    policy: py_trees.common.ParallelPolicy.Base | None = None,
) -> py_trees.composites.Parallel:
    """Create a parallel composite node."""
    if policy is None:
        policy = SuccessOnAll()
    return py_trees.composites.Parallel(name=name, policy=policy, children=children)


# Parallel policies
ParallelPolicy = py_trees.common.ParallelPolicy
SuccessOnAll = py_trees.common.ParallelPolicy.SuccessOnAll
SuccessOnOne = py_trees.common.ParallelPolicy.SuccessOnOne

# OneShot policy
OneShotPolicy = py_trees.common.OneShotPolicy

# Decorators
Inverter = py_trees.decorators.Inverter
FailureIsSuccess = py_trees.decorators.FailureIsSuccess
SuccessIsFailure = py_trees.decorators.SuccessIsFailure
Retry = py_trees.decorators.Retry
Repeat = py_trees.decorators.Repeat
Timeout = py_trees.decorators.Timeout
OneShot = py_trees.decorators.OneShot

# Behaviors
Running = py_trees.behaviours.Running
Success = py_trees.behaviours.Success
Failure = py_trees.behaviours.Failure
Dummy = py_trees.behaviours.Dummy

# Visualization
ascii_tree = py_trees.display.ascii_tree
unicode_tree = py_trees.display.unicode_tree

__all__ = [
    "Action",
    "BehaviorTreeRunner",
    "Blackboard",
    "Condition",
    "Dummy",
    "Failure",
    "FailureIsSuccess",
    "ForEach",
    "Inverter",
    "NodeStats",
    "OneShot",
    "OneShotPolicy",
    "Parallel",
    "ParallelPolicy",
    "Repeat",
    "Retry",
    "Running",
    "Selector",
    "Sequence",
    "StatsVisitor",
    "Status",
    "Success",
    "SuccessIsFailure",
    "SuccessOnAll",
    "SuccessOnOne",
    "Timeout",
    "action_node",
    "ascii_tree",
    "condition_node",
    "unicode_tree",
]
