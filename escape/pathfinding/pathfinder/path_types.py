"""Data structures for graph pathfinding results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escape.pathfinding.pathfinder.transport_metadata import TransportMetadata
    from escape.pathfinding.transport.transport import Transport


@dataclass
class PathStep:
    """A single step in the path."""

    x: int
    y: int
    plane: int
    node_id: int
    step_type: str  # 'start', 'walk', 'transport', 'teleport', 'goal'
    transport_name: str | None = None
    from_node_id: int = -1  # Origin node for edge transports
    csr_edge_index: int = -1  # CSR edge index for edge transports


@dataclass
class Segment:
    """A segment between two path steps."""

    from_step: PathStep
    to_step: PathStep
    distance: int
    segment_type: str  # 'walk', 'transport', 'teleport'


@dataclass
class PathResult:
    """Result of a pathfinding query."""

    found: bool
    total_cost: int = 0
    steps: list[PathStep] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    transports_used: list[str] = field(default_factory=list)
    transports_metadata: list[TransportMetadata] = field(default_factory=list)  # Rich metadata
    walk_distance: int = 0
    iterations: int = 0
    matched_spawns: dict[int, Transport] = field(default_factory=dict, repr=False)


@dataclass
class WalkSegment:
    """A walk segment between two critical waypoints."""

    start: tuple[int, int, int]  # (x, y, plane)
    end: tuple[int, int, int]  # (x, y, plane)
    graph_distance: int  # Estimated distance from graph
    euclidean_distance: float  # Straight-line distance


@dataclass
class DetailedPathResult:
    """Result with actual tile-by-tile paths."""

    found: bool
    total_cost: int = 0

    # Tile-by-tile path as list of (x, y, plane) tuples
    tile_path: list[tuple[int, int, int]] = field(default_factory=list)

    # Transport hops: list of (from_tile, to_tile, transport_name, node_id, from_node_id)
    transport_hops: list[tuple[tuple[int, int, int], tuple[int, int, int], str, int, int]] = field(
        default_factory=list
    )

    # Original graph result for reference
    graph_result: PathResult | None = None

    # Matched spawn transports (node_id -> Transport that qualified)
    matched_spawns: dict[int, Transport] = field(default_factory=dict, repr=False)

    # Statistics
    segments_computed: int = 0
    total_nodes_explored: int = 0
    elapsed_ms: float = 0.0
