"""Standalone functions for building path result structures from graph pathfinding output."""

from __future__ import annotations

from typing import TYPE_CHECKING

from escape.pathfinding.pathfinder.path_types import PathStep, Segment

if TYPE_CHECKING:
    import numpy as np

    from escape.pathfinding.pathfinder.transport_metadata import (
        TransportMetadata,
        TransportMetadataDB,
    )
    from escape.pathfinding.transport.transport import Transport


def get_transport_name(node_id: int, node_names: np.ndarray) -> str | None:
    """Get transport name for a node from the node_names array."""
    if 0 <= node_id < len(node_names):
        name = str(node_names[node_id])
        if name:
            return name
    return None


def get_edge_transport_info(
    from_node: int,
    to_node: int,
    edge_offsets: np.ndarray,
    edge_targets: np.ndarray,
    edge_transport_type: np.ndarray,
) -> tuple[int, int]:
    """Get the transport type and CSR edge index for the edge from from_node to to_node.

    Returns:
        (type_index, csr_index): type is 0=walk, 1+=transport, -1=not found.
            csr_index is -1 if edge not found.

    """
    if from_node < 0:
        return 0, -1  # Not a real edge

    # Look up edge in CSR structure
    start_idx = edge_offsets[from_node]
    end_idx = edge_offsets[from_node + 1]

    for j in range(start_idx, end_idx):
        if edge_targets[j] == to_node:
            return int(edge_transport_type[j]), int(j)

    return -1, -1  # Edge not found (virtual edge)


def _transport_name_from_obj(transport: Transport) -> str:
    """Get the best available name from a Transport object."""
    return transport.display_info or transport.object_info or transport.transport_type.name


def build_path_steps(
    path_nodes: list[int],
    start: tuple[int, int, int],
    goal: tuple[int, int, int],
    prev: np.ndarray,
    node_x: np.ndarray,
    node_y: np.ndarray,
    node_plane: np.ndarray,
    node_names: np.ndarray,
    edge_offsets: np.ndarray,
    edge_targets: np.ndarray,
    edge_transport_type: np.ndarray,
    bank_nodes: set[int] | None = None,
    edge_transports: dict[int, Transport] | None = None,
) -> list[PathStep]:
    """Build PathStep list from node path."""
    steps = []

    # Start step
    steps.append(PathStep(x=start[0], y=start[1], plane=start[2], node_id=-1, step_type="start"))

    # Path through nodes
    for node_id in path_nodes:
        x = int(node_x[node_id])
        y = int(node_y[node_id])
        plane = int(node_plane[node_id])
        from_node_id = -1
        csr_edge_index = -1

        # Determine step type based on how we got here
        if prev[node_id] == -3:  # Came from teleport spawn
            step_type = "teleport"
            transport_name = get_transport_name(node_id, node_names)
        elif prev[node_id] == -2:  # Came from actual start position
            step_type = "walk"
            transport_name = None
        else:
            # Check the EDGE type, not the node type!
            # A walk edge (type 0) means walking, transport edge (type > 0) means transport
            prev_node = prev[node_id]
            edge_type, csr_idx = get_edge_transport_info(
                prev_node, node_id, edge_offsets, edge_targets, edge_transport_type
            )

            if edge_type == -1:
                # Virtual edge (bank-unlocked teleport)
                step_type = "teleport"
                transport_name = get_transport_name(node_id, node_names)
            elif edge_type > 0:
                step_type = "transport"
                from_node_id = prev_node
                csr_edge_index = csr_idx
                # Get name from the actual Transport on this edge (correct per-edge)
                transport_obj = (
                    edge_transports.get(csr_idx) if edge_transports and csr_idx >= 0 else None
                )
                if transport_obj is not None:
                    transport_name = _transport_name_from_obj(transport_obj)
                else:
                    transport_name = get_transport_name(node_id, node_names)
            else:
                # This is a walk edge (even if between transport nodes)
                step_type = "walk"
                transport_name = None

        # Override walk steps at bank nodes
        if step_type == "walk" and bank_nodes and node_id in bank_nodes:
            step_type = "bank"

        steps.append(
            PathStep(
                x=x,
                y=y,
                plane=plane,
                node_id=node_id,
                step_type=step_type,
                transport_name=transport_name,
                from_node_id=from_node_id,
                csr_edge_index=csr_edge_index,
            )
        )

    # Goal step
    steps.append(PathStep(x=goal[0], y=goal[1], plane=goal[2], node_id=-2, step_type="goal"))

    return steps


def build_segments(steps: list[PathStep]) -> list[Segment]:
    """Build segments from steps."""
    segments = []

    for i in range(len(steps) - 1):
        from_step = steps[i]
        to_step = steps[i + 1]

        # Calculate distance (simple Manhattan for now)
        distance = abs(to_step.x - from_step.x) + abs(to_step.y - from_step.y)

        segment_type = to_step.step_type
        if segment_type in ("start", "goal"):
            segment_type = "walk"

        segments.append(
            Segment(
                from_step=from_step,
                to_step=to_step,
                distance=distance,
                segment_type=segment_type,
            )
        )

    return segments


def _metadata_from_transport(
    transport: Transport, node_id: int, from_node_id: int
) -> TransportMetadata:
    """Build a TransportMetadata from a Transport object for an edge."""
    from escape.pathfinding.pathfinder.transport_metadata import TransportMetadata

    origin_coords = transport.get_origin_coords()
    origin_x = origin_coords[0] if origin_coords else None
    origin_y = origin_coords[1] if origin_coords else None
    origin_plane = origin_coords[2] if origin_coords else None

    return TransportMetadata(
        node_id=from_node_id,
        transport_id=from_node_id,
        name=_transport_name_from_obj(transport),
        transport_type=transport.transport_type.name,
        x=0,
        y=0,
        plane=0,
        origin_x=origin_x,
        origin_y=origin_y,
        origin_plane=origin_plane,
        is_spawn_point=False,
        duration_ticks=transport.duration,
        display_info=transport.display_info or "",
        action=transport.object_info or "",
        is_consumable=transport.is_consumable,
    )


def extract_transports_from_steps(
    steps: list[PathStep],
    metadata_db: TransportMetadataDB | None,
    edge_transports: dict[int, Transport] | None = None,
) -> tuple[list[str], list[TransportMetadata]]:
    """Extract transport names and metadata from steps."""
    names: list[str] = []
    metadata_list: list[TransportMetadata] = []
    seen: set[int] = set()

    for step in steps:
        if step.transport_name and step.transport_name not in names:
            names.append(step.transport_name)

        if step.step_type not in ("teleport", "transport"):
            continue

        # For edge transports with a CSR index, build metadata from the Transport object
        if step.step_type == "transport" and step.csr_edge_index >= 0 and edge_transports:
            if step.csr_edge_index not in seen:
                transport_obj = edge_transports.get(step.csr_edge_index)
                if transport_obj is not None:
                    metadata_list.append(
                        _metadata_from_transport(transport_obj, step.node_id, step.from_node_id)
                    )
                    seen.add(step.csr_edge_index)
            continue

        # Fallback: use metadata_db (for teleports / spawn transports)
        meta_node = step.from_node_id if step.from_node_id >= 0 else step.node_id
        if meta_node >= 0 and meta_node not in seen:
            meta_entries = metadata_db.get(meta_node) if metadata_db is not None else None
            if meta_entries is not None:
                metadata_list.extend(meta_entries)
                seen.add(meta_node)

    return names, metadata_list
