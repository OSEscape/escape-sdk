from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class TreeNode:
    info: Any = None
    type: str = ""
    status: str = ""
    parent: int | None = None
    children: list[int] = field(default_factory=list)
    state: Any = None
    action: Any = None
    selected_method: Any = None
    available_methods: Iterator[Any] | None = None
    methods: list[Any] | None = None
    tag: str = ""


class DecompositionTree:
    def __init__(self) -> None:
        self._nodes: dict[int, TreeNode] = {}

    def __getitem__(self, node_id: int) -> TreeNode:
        return self._nodes[node_id]

    def __contains__(self, node_id: int) -> bool:
        return node_id in self._nodes

    def add_node(self, node_id: int, node: TreeNode) -> None:
        self._nodes[node_id] = node

    def add_edge(self, parent: int, child: int) -> None:
        self._nodes[parent].children.append(child)
        self._nodes[child].parent = parent

    def successors(self, node_id: int) -> list[int]:
        return self._nodes[node_id].children

    def predecessor(self, node_id: int) -> int | None:
        return self._nodes[node_id].parent

    def dfs_preorder(self, source: int) -> list[int]:
        result: list[int] = []
        stack = deque([source])
        while stack:
            nid = stack.pop()
            if nid not in self._nodes:
                continue
            result.append(nid)
            for child in reversed(self._nodes[nid].children):
                stack.append(child)
        return result

    def descendants(self, node_id: int) -> list[int]:
        result = self.dfs_preorder(node_id)
        return result[1:]  # exclude the node itself

    def remove_nodes(self, node_ids: list[int]) -> None:
        to_remove = set(node_ids)
        for nid in node_ids:
            node = self._nodes.get(nid)
            if node is None:
                continue
            if node.parent is not None and node.parent in self._nodes:
                parent = self._nodes[node.parent]
                parent.children = [c for c in parent.children if c not in to_remove]
        for nid in node_ids:
            self._nodes.pop(nid, None)

    @property
    def nodes(self) -> dict[int, TreeNode]:
        return self._nodes
