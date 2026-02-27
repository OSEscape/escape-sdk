"""Dijkstra implementation for CSR graph format.

Prefers Rust native extension for zero cold-start latency; falls back to
Numba JIT if the native module is not available.
"""

from __future__ import annotations

try:
    from escape.pathfinding._native import dijkstra_csr as _dijkstra_csr
    from escape.pathfinding._native import dijkstra_csr_multi_target as _dijkstra_csr_multi_target
except ImportError:
    import numpy as np
    from numba import njit

    @njit(cache=True)
    def _heap_push(heap_costs, heap_nodes, heap_size, max_heap_size, cost, node):
        """Push a (cost, node) pair onto the min-heap. Returns new heap_size."""
        if heap_size >= max_heap_size:
            return heap_size

        heap_costs[heap_size] = cost
        heap_nodes[heap_size] = node
        heap_size += 1

        # Bubble up
        idx = heap_size - 1
        while idx > 0:
            parent = (idx - 1) // 2
            if heap_costs[idx] < heap_costs[parent]:
                heap_costs[idx], heap_costs[parent] = heap_costs[parent], heap_costs[idx]
                heap_nodes[idx], heap_nodes[parent] = heap_nodes[parent], heap_nodes[idx]
                idx = parent
            else:
                break

        return heap_size

    @njit(cache=True)
    def _dijkstra_csr(
        start_node: int,
        goal_node: int,
        edge_offsets: np.ndarray,
        edge_targets: np.ndarray,
        edge_weights: np.ndarray,
        virtual_edge_targets: np.ndarray,
        virtual_edge_weights: np.ndarray,
        start_walk_cost: int,
        edge_blocked: np.ndarray,
        bank_node_ids: np.ndarray,
        bank_virtual_targets: np.ndarray,
        bank_virtual_weights: np.ndarray,
        edge_bank_unblockable: np.ndarray,
        max_iterations: int = 1000000,
    ) -> tuple[np.ndarray, np.ndarray, int, bool]:
        """Dijkstra with virtual edges for teleports and bank-aware unlocking."""
        num_nodes = len(edge_offsets) - 1
        inf = 2147483647

        dist = np.full(num_nodes, inf, dtype=np.int32)
        prev = np.full(num_nodes, -1, dtype=np.int32)

        heap_size = 0
        max_heap_size = min(num_nodes * 2, 500000)
        heap_costs = np.empty(max_heap_size, dtype=np.int32)
        heap_nodes = np.empty(max_heap_size, dtype=np.int32)

        dist[start_node] = start_walk_cost
        prev[start_node] = -2

        heap_costs[0] = start_walk_cost
        heap_nodes[0] = start_node
        heap_size = 1

        for i in range(len(virtual_edge_targets)):
            target = virtual_edge_targets[i]
            cost = virtual_edge_weights[i]
            if target < num_nodes and cost < dist[target]:
                dist[target] = cost
                prev[target] = -3

                heap_size = _heap_push(
                    heap_costs, heap_nodes, heap_size, max_heap_size, cost, target
                )

        iterations = 0
        found = False
        bank_visited = False
        has_bank_nodes = len(bank_node_ids) > 0

        while heap_size > 0 and iterations < max_iterations:
            iterations += 1

            cost = heap_costs[0]
            node = heap_nodes[0]

            heap_size -= 1
            if heap_size > 0:
                heap_costs[0] = heap_costs[heap_size]
                heap_nodes[0] = heap_nodes[heap_size]

                idx = 0
                while True:
                    left = 2 * idx + 1
                    right = 2 * idx + 2
                    smallest = idx

                    if left < heap_size and heap_costs[left] < heap_costs[smallest]:
                        smallest = left
                    if right < heap_size and heap_costs[right] < heap_costs[smallest]:
                        smallest = right

                    if smallest != idx:
                        heap_costs[idx], heap_costs[smallest] = (
                            heap_costs[smallest],
                            heap_costs[idx],
                        )
                        heap_nodes[idx], heap_nodes[smallest] = (
                            heap_nodes[smallest],
                            heap_nodes[idx],
                        )
                        idx = smallest
                    else:
                        break

            if cost > dist[node]:
                continue

            if node == goal_node:
                found = True
                break

            if not bank_visited and has_bank_nodes:
                bi = np.searchsorted(bank_node_ids, node)
                if bi < len(bank_node_ids) and bank_node_ids[bi] == node:
                    bank_visited = True
                    for i in range(len(bank_virtual_targets)):
                        target = bank_virtual_targets[i]
                        weight = bank_virtual_weights[i]
                        new_cost = cost + weight
                        if target < num_nodes and new_cost < dist[target]:
                            dist[target] = new_cost
                            prev[target] = node

                            heap_size = _heap_push(
                                heap_costs,
                                heap_nodes,
                                heap_size,
                                max_heap_size,
                                new_cost,
                                target,
                            )

            start_idx = edge_offsets[node]
            end_idx = edge_offsets[node + 1]

            for j in range(start_idx, end_idx):
                if edge_blocked[j] and not (bank_visited and edge_bank_unblockable[j]):
                    continue

                neighbor = edge_targets[j]
                weight = edge_weights[j]
                new_cost = cost + weight

                if new_cost < dist[neighbor]:
                    dist[neighbor] = new_cost
                    prev[neighbor] = node

                    heap_size = _heap_push(
                        heap_costs, heap_nodes, heap_size, max_heap_size, new_cost, neighbor
                    )

        return dist, prev, iterations, found

    @njit(cache=True)
    def _dijkstra_csr_multi_target(
        start_node: int,
        target_node_ids: np.ndarray,
        edge_offsets: np.ndarray,
        edge_targets: np.ndarray,
        edge_weights: np.ndarray,
        virtual_edge_targets: np.ndarray,
        virtual_edge_weights: np.ndarray,
        start_walk_cost: int,
        edge_blocked: np.ndarray,
        max_iterations: int = 1000000,
    ) -> tuple[np.ndarray, np.ndarray, int, bool, int]:
        """Dijkstra that terminates when ANY target node is popped."""
        num_nodes = len(edge_offsets) - 1
        inf = 2147483647

        dist = np.full(num_nodes, inf, dtype=np.int32)
        prev = np.full(num_nodes, -1, dtype=np.int32)

        heap_size = 0
        max_heap_size = min(num_nodes * 2, 500000)
        heap_costs = np.empty(max_heap_size, dtype=np.int32)
        heap_nodes = np.empty(max_heap_size, dtype=np.int32)

        dist[start_node] = start_walk_cost
        prev[start_node] = -2

        heap_costs[0] = start_walk_cost
        heap_nodes[0] = start_node
        heap_size = 1

        for i in range(len(virtual_edge_targets)):
            target = virtual_edge_targets[i]
            cost = virtual_edge_weights[i]
            if target < num_nodes and cost < dist[target]:
                dist[target] = cost
                prev[target] = -3

                heap_size = _heap_push(
                    heap_costs, heap_nodes, heap_size, max_heap_size, cost, target
                )

        iterations = 0
        found = False
        found_node = -1

        while heap_size > 0 and iterations < max_iterations:
            iterations += 1

            cost = heap_costs[0]
            node = heap_nodes[0]

            heap_size -= 1
            if heap_size > 0:
                heap_costs[0] = heap_costs[heap_size]
                heap_nodes[0] = heap_nodes[heap_size]

                idx = 0
                while True:
                    left = 2 * idx + 1
                    right = 2 * idx + 2
                    smallest = idx

                    if left < heap_size and heap_costs[left] < heap_costs[smallest]:
                        smallest = left
                    if right < heap_size and heap_costs[right] < heap_costs[smallest]:
                        smallest = right

                    if smallest != idx:
                        heap_costs[idx], heap_costs[smallest] = (
                            heap_costs[smallest],
                            heap_costs[idx],
                        )
                        heap_nodes[idx], heap_nodes[smallest] = (
                            heap_nodes[smallest],
                            heap_nodes[idx],
                        )
                        idx = smallest
                    else:
                        break

            if cost > dist[node]:
                continue

            bi = np.searchsorted(target_node_ids, node)
            if bi < len(target_node_ids) and target_node_ids[bi] == node:
                found = True
                found_node = node
                break

            start_idx = edge_offsets[node]
            end_idx = edge_offsets[node + 1]

            for j in range(start_idx, end_idx):
                if edge_blocked[j]:
                    continue

                neighbor = edge_targets[j]
                weight = edge_weights[j]
                new_cost = cost + weight

                if new_cost < dist[neighbor]:
                    dist[neighbor] = new_cost
                    prev[neighbor] = node

                    heap_size = _heap_push(
                        heap_costs, heap_nodes, heap_size, max_heap_size, new_cost, neighbor
                    )

        return dist, prev, iterations, found, found_node
