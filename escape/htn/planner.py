from __future__ import annotations

from copy import deepcopy
from itertools import count
from typing import TYPE_CHECKING, Any

from escape.htn._tree import DecompositionTree, TreeNode
from escape.htn.state import MultiGoal, State, goals_not_achieved

if TYPE_CHECKING:
    from collections.abc import Callable

    from escape.htn.domain import Domain


class Planner:
    def __init__(self, domain: Domain) -> None:
        self.domain = domain
        self.methods = domain.methods
        self.actions = domain.actions
        self.state: State | None = None
        self.task_list: list[tuple[Any, ...] | MultiGoal] = []
        self.sol_plan: list[tuple[Any, ...]] = []
        self._sol_node_ids: list[int] = []
        self.sol_tree = DecompositionTree()
        self.blacklist: set[tuple[Any, ...]] = set()
        self.iterations: int = 0

    def plan(
        self,
        state: State,
        task_list: list[tuple[Any, ...] | MultiGoal],
    ) -> list[tuple[Any, ...]]:
        self.state = state.copy()
        self.task_list = deepcopy(task_list)  # type: ignore[assignment]

        self.sol_plan = []
        self._sol_node_ids = []
        self.sol_tree = DecompositionTree()

        _id = 0
        parent_node_id = _id
        self.sol_tree.add_node(_id, TreeNode(info=("root",), type="D", status="NA"))
        _id = self._add_nodes_and_edges(_id, _id, self.task_list)

        self.iterations = self._planning(_id, parent_node_id)

        for node_id in self.sol_tree.dfs_preorder(0):
            node = self.sol_tree[node_id]
            if node.type == "A":
                self.sol_plan.append(node.info)
                self._sol_node_ids.append(node_id)

        return self.sol_plan

    def _planning(self, _id: int, parent_node_id: int) -> int:
        assert self.state is not None

        _iter = 0
        for _iter in count(0):
            curr_node_id: int | None = None
            for node_id in self.sol_tree.successors(parent_node_id):
                if self.sol_tree[node_id].status == "O":
                    curr_node_id = node_id
                    break

            if curr_node_id is None:
                pred = self.sol_tree.predecessor(parent_node_id)
                if pred is None:
                    break
                parent_node_id = pred
            else:
                curr_node = self.sol_tree[curr_node_id]
                if curr_node.state is not None:
                    self.state.update(curr_node.state.copy())
                elif hasattr(curr_node, "state"):
                    curr_node.state = self.state.copy()

                curr_node_info = curr_node.info

                if curr_node.type == "T":
                    subtasks = None
                    assert curr_node.available_methods is not None
                    for method in curr_node.available_methods:
                        curr_node.selected_method = method
                        subtasks = method(self.state, *curr_node_info[1:])
                        if subtasks is not None:
                            curr_node.status = "C"
                            _id = self._add_nodes_and_edges(_id, curr_node_id, subtasks)
                            parent_node_id = curr_node_id
                            break
                    if subtasks is None:
                        parent_node_id, curr_node_id = self._backtrack(parent_node_id, curr_node_id)

                elif curr_node.type == "A":
                    new_state = None
                    if curr_node_info not in self.blacklist:
                        new_state = curr_node.action(self.state.copy(), *curr_node_info[1:])
                        if new_state is not None:
                            curr_node.status = "C"
                            self.state.update(new_state)
                    if new_state is None:
                        parent_node_id, curr_node_id = self._backtrack(parent_node_id, curr_node_id)

                elif curr_node.type == "G":
                    subgoals = None
                    state_var, arg, desired_val = curr_node_info
                    if getattr(self.state, state_var)[arg] == desired_val:
                        curr_node.status = "C"
                        subgoals = []
                    else:
                        assert curr_node.available_methods is not None
                        for method in curr_node.available_methods:
                            curr_node.selected_method = method
                            subgoals = method(self.state, *curr_node_info[1:])
                            if subgoals is not None:
                                curr_node.status = "C"
                                _id = self._add_nodes_and_edges(_id, curr_node_id, subgoals)
                                parent_node_id = curr_node_id
                                break
                    if subgoals is None:
                        parent_node_id, curr_node_id = self._backtrack(parent_node_id, curr_node_id)

                elif curr_node.type == "M":
                    subgoals = None
                    unachieved_goals = self._goals_not_achieved(curr_node_id)
                    if not unachieved_goals:
                        curr_node.status = "C"
                        subgoals = []
                    else:
                        assert curr_node.available_methods is not None
                        for method in curr_node.available_methods:
                            curr_node.selected_method = method
                            subgoals = method(self.state, curr_node_info)
                            if subgoals is not None:
                                curr_node.status = "C"
                                _id = self._add_nodes_and_edges(_id, curr_node_id, subgoals)
                                parent_node_id = curr_node_id
                                break
                    if subgoals is None:
                        parent_node_id, curr_node_id = self._backtrack(parent_node_id, curr_node_id)

                elif curr_node.type == "VG":
                    state_var, arg, desired_val = self.sol_tree[parent_node_id].info
                    if getattr(self.state, state_var)[arg] == desired_val:
                        curr_node.status = "C"
                    else:
                        parent_node_id, curr_node_id = self._backtrack(parent_node_id, curr_node_id)

                elif curr_node.type == "VM":
                    unachieved_goals = self._goals_not_achieved(parent_node_id)
                    if not unachieved_goals:
                        curr_node.status = "C"
                    else:
                        parent_node_id, curr_node_id = self._backtrack(parent_node_id, curr_node_id)

        return _iter

    def replan(self, state: State, fail_node_id: int) -> list[tuple[Any, ...]]:
        self.state = state.copy()

        max_id = self._post_failure_modify(fail_node_id)
        parent = self.sol_tree.predecessor(fail_node_id)
        assert parent is not None
        parent_node_id, _ = self._backtrack(parent, fail_node_id)

        self.iterations = self._planning(max_id, parent_node_id)

        self.sol_plan = []
        self._sol_node_ids = []
        for node_id in self.sol_tree.dfs_preorder(0):
            node = self.sol_tree[node_id]
            if node.type == "A" and node.tag == "new":
                self.sol_plan.append(node.info)
                self._sol_node_ids.append(node_id)

        return self.sol_plan

    def _add_nodes_and_edges(
        self,
        _id: int,
        parent_node_id: int,
        children_node_info_list: list[Any],
    ) -> int:
        for child_node_info in children_node_info_list:
            _id += 1
            if isinstance(child_node_info, MultiGoal):
                relevant_methods = self.methods.multigoals[child_node_info.goal_tag]
                self.sol_tree.add_node(
                    _id,
                    TreeNode(
                        info=child_node_info,
                        type="M",
                        status="O",
                        selected_method=None,
                        available_methods=iter(relevant_methods),
                        methods=relevant_methods,
                        tag="new",
                    ),
                )
                self.sol_tree.add_edge(parent_node_id, _id)
            elif child_node_info[0] in self.methods.tasks:
                relevant_methods = self.methods.tasks[child_node_info[0]]
                self.sol_tree.add_node(
                    _id,
                    TreeNode(
                        info=child_node_info,
                        type="T",
                        status="O",
                        selected_method=None,
                        available_methods=iter(relevant_methods),
                        methods=relevant_methods,
                        tag="new",
                    ),
                )
                self.sol_tree.add_edge(parent_node_id, _id)
            elif child_node_info[0] in self.actions.action_dict:
                action = self.actions.action_dict[child_node_info[0]]
                self.sol_tree.add_node(
                    _id,
                    TreeNode(info=child_node_info, type="A", status="O", action=action, tag="new"),
                )
                self.sol_tree.add_edge(parent_node_id, _id)
            elif child_node_info[0] in self.methods.goals:
                relevant_methods = self.methods.goals[child_node_info[0]]
                self.sol_tree.add_node(
                    _id,
                    TreeNode(
                        info=child_node_info,
                        type="G",
                        status="O",
                        selected_method=None,
                        available_methods=iter(relevant_methods),
                        methods=relevant_methods,
                        tag="new",
                    ),
                )
                self.sol_tree.add_edge(parent_node_id, _id)

        parent_node = self.sol_tree[parent_node_id]
        if parent_node.type == "G":
            _id += 1
            self.sol_tree.add_node(
                _id, TreeNode(info="VerifyGoal", type="VG", status="O", tag="new")
            )
            self.sol_tree.add_edge(parent_node_id, _id)
        elif parent_node.type == "M":
            _id += 1
            self.sol_tree.add_node(
                _id, TreeNode(info="VerifyMultiGoal", type="VM", status="O", tag="new")
            )
            self.sol_tree.add_edge(parent_node_id, _id)

        return _id

    def _post_failure_modify(self, fail_node_id: int) -> int:
        rev_pre_ord_nodes = reversed(self.sol_tree.dfs_preorder(0))

        for node_id in rev_pre_ord_nodes:
            c_node = self.sol_tree[node_id]
            c_node.status = "O"

            if node_id == fail_node_id:
                break

            c_type = c_node.type
            if c_type in ("T", "G", "M"):
                c_node.state = None
                c_node.selected_method = None
                assert c_node.methods is not None
                c_node.available_methods = iter(c_node.methods)
                descendant_list = self.sol_tree.descendants(node_id)
                self.sol_tree.remove_nodes(descendant_list)

        max_id = -1
        for node_id, node in self.sol_tree.nodes.items():
            if node_id >= max_id:
                max_id = node_id + 1
            if node.state is not None or node.type in ("T", "G", "M"):
                if node.status == "C":
                    assert self.state is not None
                    node.state = self.state.copy()
                else:
                    node.state = None
            if node.status == "C":
                node.tag = "old"

        return max_id

    def _backtrack(self, p_node_id: int, c_node_id: int) -> tuple[int, int]:
        c_node = self.sol_tree[c_node_id]
        c_type = c_node.type
        if c_type in ("T", "G", "M"):
            c_node.state = None
            c_node.selected_method = None
            assert c_node.methods is not None
            c_node.available_methods = iter(c_node.methods)

        dfs_list = self.sol_tree.dfs_preorder(p_node_id)
        for node_id in reversed(dfs_list):
            node = self.sol_tree[node_id]
            if node.status == "C":
                node.status = "O"
                descendant_list = self.sol_tree.descendants(node_id)
                if descendant_list:
                    self.sol_tree.remove_nodes(descendant_list)
                    pred = self.sol_tree.predecessor(node_id)
                    assert pred is not None
                    return pred, node_id
                if node.state is not None or node.type in ("T", "G", "M"):
                    node.state = None

        self.sol_tree.remove_nodes(self.sol_tree.descendants(0))
        return 0, 0

    def _goals_not_achieved(self, multigoal_node_id: int) -> dict[str, dict[str, Any]]:
        assert self.state is not None
        multigoal = self.sol_tree[multigoal_node_id].info
        return goals_not_achieved(self.state, multigoal)

    def execute(self, observe: Callable[[], State], max_retries: int = 3) -> bool:
        for _ in range(max_retries):
            for node_id, action in zip(self._sol_node_ids, self.sol_plan, strict=True):
                action_name, *args = action
                executor = self.actions.executor_dict.get(action_name)
                if executor is None:
                    return False
                if not executor(*args):
                    real_state = observe()
                    self.blacklist_command(action)
                    self.replan(real_state, node_id)
                    break
            else:
                return True
        return False

    def simulate(self, state: State, start_ind: int = 0) -> list[State]:
        state_list = [state.copy()]
        state_copy = state.copy()
        plan = self.sol_plan[start_ind:]
        for action in plan:
            self.actions.action_dict[action[0]](state_copy, *action[1:])
            state_list.append(state_copy.copy())
        return state_list

    def blacklist_command(self, command: tuple[Any, ...]) -> None:
        self.blacklist.add(command)
