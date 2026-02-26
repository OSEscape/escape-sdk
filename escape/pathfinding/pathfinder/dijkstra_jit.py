"""Numba-accelerated Dijkstra implementation for CSR graph format."""

from __future__ import annotations

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
    virtual_edge_targets: np.ndarray,  # Teleport destinations reachable from start
    virtual_edge_weights: np.ndarray,  # Teleport activation costs
    start_walk_cost: int,
    edge_blocked: np.ndarray,  # bool array, True = blocked
    bank_node_ids: np.ndarray,  # sorted node IDs of bank locations
    bank_virtual_targets: np.ndarray,  # teleport targets unlocked after visiting bank
    bank_virtual_weights: np.ndarray,  # costs for bank-unlocked teleports
    edge_bank_unblockable: np.ndarray,  # bool array, True = unblocked after bank visit
    max_iterations: int = 1000000,
) -> tuple[np.ndarray, np.ndarray, int, bool]:
    """Dijkstra with virtual edges for teleports and bank-aware unlocking."""
    num_nodes = len(edge_offsets) - 1
    inf = 2147483647

    # Distance and predecessor arrays
    dist = np.full(num_nodes, inf, dtype=np.int32)
    prev = np.full(num_nodes, -1, dtype=np.int32)

    # Simple array-based heap (cost, node)
    # Using parallel arrays for Numba compatibility
    heap_size = 0
    max_heap_size = min(num_nodes * 2, 500000)
    heap_costs = np.empty(max_heap_size, dtype=np.int32)
    heap_nodes = np.empty(max_heap_size, dtype=np.int32)

    # Initialize: walk from start
    dist[start_node] = start_walk_cost
    prev[start_node] = -2  # Special marker: came from actual start position

    # Push start to heap
    heap_costs[0] = start_walk_cost
    heap_nodes[0] = start_node
    heap_size = 1

    # Add virtual edges from start to teleport destinations
    # These are treated as neighbors of the START POSITION (not start_node)
    for i in range(len(virtual_edge_targets)):
        target = virtual_edge_targets[i]
        cost = virtual_edge_weights[i]  # Teleport activation cost
        if target < num_nodes and cost < dist[target]:
            dist[target] = cost
            prev[target] = -3  # Special marker: came from teleport

            heap_size = _heap_push(heap_costs, heap_nodes, heap_size, max_heap_size, cost, target)

    iterations = 0
    found = False
    bank_visited = False
    has_bank_nodes = len(bank_node_ids) > 0

    # Main Dijkstra loop
    while heap_size > 0 and iterations < max_iterations:
        iterations += 1

        # Pop minimum (manual heap pop for Numba)
        cost = heap_costs[0]
        node = heap_nodes[0]

        # Move last element to root and bubble down
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
                    heap_costs[idx], heap_costs[smallest] = heap_costs[smallest], heap_costs[idx]
                    heap_nodes[idx], heap_nodes[smallest] = heap_nodes[smallest], heap_nodes[idx]
                    idx = smallest
                else:
                    break

        # Skip if we've found a better path
        if cost > dist[node]:
            continue

        # Check if reached goal
        if node == goal_node:
            found = True
            break

        # Bank unlock: first time we pop a bank node
        if not bank_visited and has_bank_nodes:
            bi = np.searchsorted(bank_node_ids, node)
            if bi < len(bank_node_ids) and bank_node_ids[bi] == node:
                bank_visited = True
                # Inject bank-unlocked teleport virtual edges
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

        # Explore neighbors (CSR pattern)
        start_idx = edge_offsets[node]
        end_idx = edge_offsets[node + 1]

        for j in range(start_idx, end_idx):
            # Skip blocked edges (unless bank-visited and edge is bank-unblockable)
            if edge_blocked[j] and not (bank_visited and edge_bank_unblockable[j]):
                continue

            neighbor = edge_targets[j]
            weight = edge_weights[j]
            new_cost = cost + weight

            if new_cost < dist[neighbor]:
                dist[neighbor] = new_cost
                prev[neighbor] = node

                # Push to heap
                heap_size = _heap_push(
                    heap_costs, heap_nodes, heap_size, max_heap_size, new_cost, neighbor
                )

    return dist, prev, iterations, found


@njit(cache=True)
def _dijkstra_csr_multi_target(
    start_node: int,
    target_node_ids: np.ndarray,  # sorted array of goal node IDs (any match terminates)
    edge_offsets: np.ndarray,
    edge_targets: np.ndarray,
    edge_weights: np.ndarray,
    virtual_edge_targets: np.ndarray,
    virtual_edge_weights: np.ndarray,
    start_walk_cost: int,
    edge_blocked: np.ndarray,
    max_iterations: int = 1000000,
) -> tuple[np.ndarray, np.ndarray, int, bool, int]:
    """Dijkstra that terminates when ANY target node is popped.

    Simpler than _dijkstra_csr — no bank-unlocking logic (we're searching
    FOR a bank, not routing through one).

    Returns (dist, prev, iterations, found, found_node).
    """
    num_nodes = len(edge_offsets) - 1
    inf = 2147483647

    dist = np.full(num_nodes, inf, dtype=np.int32)
    prev = np.full(num_nodes, -1, dtype=np.int32)

    heap_size = 0
    max_heap_size = min(num_nodes * 2, 500000)
    heap_costs = np.empty(max_heap_size, dtype=np.int32)
    heap_nodes = np.empty(max_heap_size, dtype=np.int32)

    # Initialize start
    dist[start_node] = start_walk_cost
    prev[start_node] = -2  # came from actual start position

    heap_costs[0] = start_walk_cost
    heap_nodes[0] = start_node
    heap_size = 1

    # Add virtual edges (teleports)
    for i in range(len(virtual_edge_targets)):
        target = virtual_edge_targets[i]
        cost = virtual_edge_weights[i]
        if target < num_nodes and cost < dist[target]:
            dist[target] = cost
            prev[target] = -3  # came from teleport

            heap_size = _heap_push(heap_costs, heap_nodes, heap_size, max_heap_size, cost, target)

    iterations = 0
    found = False
    found_node = -1

    while heap_size > 0 and iterations < max_iterations:
        iterations += 1

        # Pop minimum
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
                    heap_costs[idx], heap_costs[smallest] = heap_costs[smallest], heap_costs[idx]
                    heap_nodes[idx], heap_nodes[smallest] = heap_nodes[smallest], heap_nodes[idx]
                    idx = smallest
                else:
                    break

        if cost > dist[node]:
            continue

        # Check if this node is in the target set
        bi = np.searchsorted(target_node_ids, node)
        if bi < len(target_node_ids) and target_node_ids[bi] == node:
            found = True
            found_node = node
            break

        # Explore neighbors
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
