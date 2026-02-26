"""Factory functions for loading GraphPathfinder from disk."""

from __future__ import annotations

import pickle
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from escape._logger import logger
from escape.pathfinding.core.world_point import pack_world_point
from escape.pathfinding.pathfinder.numba_pathfinder import NumbaPathfinder
from escape.pathfinding.pathfinder.transport_metadata import TransportMetadataDB

if TYPE_CHECKING:
    from escape.pathfinding.pathfinder.graph_pathfinder import GraphPathfinder


def _register_pickle_aliases() -> None:
    """Register module aliases so pickles from osrs_graph_builder can be loaded."""
    if "osrs_graph_builder" in sys.modules:
        return

    import escape.pathfinding.core.enums as enums_mod
    import escape.pathfinding.transport.transport as transport_mod

    alias_map = {
        "osrs_graph_builder": [],
        "osrs_graph_builder.transport": [],
        "osrs_graph_builder.transport.transport": transport_mod,
        "osrs_graph_builder.core": [],
        "osrs_graph_builder.core.enums": enums_mod,
    }

    for mod_name, source in alias_map.items():
        mod = types.ModuleType(mod_name)
        if isinstance(source, list):
            mod.__path__ = []  # type: ignore[attr-defined]
        else:
            for attr in dir(source):
                obj = getattr(source, attr)
                if isinstance(obj, type):
                    setattr(mod, attr, obj)
        sys.modules[mod_name] = mod


def load_graph_pathfinder(output_dir: str | Path) -> GraphPathfinder:
    """Load GraphPathfinder from output directory."""
    from escape.pathfinding.pathfinder.graph_pathfinder import GraphPathfinder

    output_dir = Path(output_dir)

    # Load graph.npz
    logger.info("Loading graph from %s...", output_dir / "graph.npz")
    graph = np.load(output_dir / "graph.npz")

    node_x = graph["node_x"]
    node_y = graph["node_y"]
    node_plane = graph["node_plane"]
    node_is_skeleton = graph["node_is_skeleton"]
    node_is_spawn = graph["node_is_spawn"]
    node_names = (
        graph["node_names"]
        if "node_names" in graph.files
        else np.array([""] * len(node_x), dtype="U64")
    )
    num_skeleton = int(graph["num_skeleton"][0])
    num_nodes = int(graph["num_nodes"][0])
    edge_offsets = graph["edge_offsets"]
    edge_targets = graph["edge_targets"]
    edge_weights = graph["edge_weights"]
    # Load edge transport type (0 = walk, 1+ = transport type index)
    edge_transport_type = (
        graph["edge_transport_type"]
        if "edge_transport_type" in graph.files
        else np.zeros(len(edge_targets), dtype=np.uint8)
    )
    skeleton_packed = graph["skeleton_packed"]
    skeleton_node_ids = graph["skeleton_node_ids"]
    spawn_node_ids = graph["spawn_node_ids"]
    spawn_costs = graph["spawn_costs"]
    edges_with_req = graph["edges_with_req"]

    # Load bank node IDs from destination_categories
    if "destination_categories" in graph.files:
        destination_categories = graph["destination_categories"]
        bank_node_ids = np.sort(np.where(destination_categories == "bank")[0].astype(np.int32))
    else:
        bank_node_ids = np.array([], dtype=np.int32)

    logger.debug("  Nodes: %d (%d skeleton)", num_nodes, num_skeleton)
    logger.debug("  Edges: %d", len(edge_targets))
    logger.debug("  Spawn points: %d", len(spawn_node_ids))
    logger.debug("  Bank nodes: %d", len(bank_node_ids))

    # Build combined graph_packed and graph_node_ids arrays
    # These include ALL nodes that can be BFS targets (skeleton + transport + spawn)
    # All nodes are searchable - spawn nodes are walkable destinations too!
    searchable_mask = np.ones(len(node_x), dtype=bool)
    graph_node_ids = np.where(searchable_mask)[0].astype(np.int32)

    # Compute packed coordinates for all searchable nodes
    graph_packed_list = []
    for node_id in graph_node_ids:
        packed = pack_world_point(
            int(node_x[node_id]), int(node_y[node_id]), int(node_plane[node_id])
        )
        graph_packed_list.append(packed)
    graph_packed_unsorted = np.array(graph_packed_list, dtype=np.int64)

    # Sort by packed coordinate for binary search
    sort_order = np.argsort(graph_packed_unsorted)
    graph_packed = graph_packed_unsorted[sort_order]
    graph_node_ids = graph_node_ids[sort_order]

    num_transport = np.sum(~node_is_skeleton & ~node_is_spawn)
    num_spawn = np.sum(node_is_spawn)
    logger.debug(
        "  Searchable nodes: %d (%d skeleton + %d transport + %d spawn)",
        len(graph_node_ids),
        num_skeleton,
        num_transport,
        num_spawn,
    )

    # Load transports.pkl
    logger.info("Loading transports from %s...", output_dir / "transports.pkl")
    _register_pickle_aliases()
    with open(output_dir / "transports.pkl", "rb") as f:
        transports_data = pickle.load(f)

    edge_transports = transports_data.get("edge_transports", {})
    spawn_transports = transports_data.get("spawn_transports", {})
    logger.debug("  Edge transports: %d", len(edge_transports))
    logger.debug("  Spawn transports: %d", len(spawn_transports))

    # Load transport metadata database
    metadata_path = output_dir / "transport_metadata.pkl"
    if metadata_path.exists():
        logger.info("Loading metadata from %s...", metadata_path)
        metadata_db = TransportMetadataDB.load(metadata_path)
        logger.debug("  Transport metadata: %d entries", len(metadata_db))
    else:
        logger.debug("  No metadata file found, metadata will be unavailable")
        metadata_db = None

    # Load NumbaPathfinder for BFS from collision-map.zip (has overrides applied)
    collision_zip = output_dir / "collision-map.zip"
    logger.info("Loading collision data from %s...", collision_zip)
    from escape.pathfinding.pathfinder.split_flag_map import SplitFlagMap

    collision_data = SplitFlagMap.from_zip_file(collision_zip)
    logger.info("Creating NumbaPathfinder from collision data...")
    numba_pathfinder = NumbaPathfinder.from_collision_data(collision_data)

    instance = GraphPathfinder(
        node_x=node_x,
        node_y=node_y,
        node_plane=node_plane,
        node_is_skeleton=node_is_skeleton,
        node_is_spawn=node_is_spawn,
        node_names=node_names,
        num_skeleton=num_skeleton,
        num_nodes=num_nodes,
        edge_offsets=edge_offsets,
        edge_targets=edge_targets,
        edge_weights=edge_weights,
        edge_transport_type=edge_transport_type,
        skeleton_packed=skeleton_packed,
        skeleton_node_ids=skeleton_node_ids,
        graph_packed=graph_packed,
        graph_node_ids=graph_node_ids,
        spawn_node_ids=spawn_node_ids,
        spawn_costs=spawn_costs,
        edges_with_req=edges_with_req,
        bank_node_ids=bank_node_ids,
        edge_transports=edge_transports,
        spawn_transports=spawn_transports,
        metadata_db=metadata_db,
        numba_pathfinder=numba_pathfinder,
    )

    # Warmup JIT-compiled functions to avoid first-query latency
    logger.info("Warming up JIT...")
    instance._warmup_jit()

    return instance
