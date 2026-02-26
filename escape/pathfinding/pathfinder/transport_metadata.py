"""Transport metadata storage for display and debugging."""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TransportMetadata:
    """Rich metadata for a transport node.

    Contains all information needed for display and debugging,
    but NOT used for pathfinding requirement checks (that's separate).
    """

    # Identifiers
    node_id: int  # Unified graph node ID
    transport_id: int  # Original transport node ID (from transport_nodes.csv)

    # Basic info
    name: str  # Human-readable name (e.g., "Ardougne tablet", "Fairy ring AIQ")
    transport_type: str  # Type name (e.g., "TELEPORTATION_ITEM", "FAIRY_RING")

    # Location
    x: int
    y: int
    plane: int

    # Origin (for fixed-origin transports)
    origin_x: int | None = None
    origin_y: int | None = None
    origin_plane: int | None = None

    # Transport properties
    is_spawn_point: bool = False  # True = teleport (anywhere -> here)
    activation_cost: int = 0  # Cost in tiles-equivalent
    duration_ticks: int = 0  # Original duration in game ticks

    # Requirements (for display only)
    skill_requirements: dict[str, int] = field(default_factory=dict)  # skill_name -> level
    quest_requirements: list[str] = field(default_factory=list)
    item_requirements: list[int] = field(default_factory=list)  # Item IDs
    varbit_requirements: list[tuple[int, int, str]] = field(
        default_factory=list
    )  # (id, value, check_type)
    varplayer_requirements: list[tuple[int, int, str]] = field(default_factory=list)
    max_wilderness_level: int = -1  # -1 = no limit

    # Extra info
    display_info: str = ""  # Original display_info from Transport
    action: str = ""  # Action verb (e.g., "Teleport", "Climb", "Use")
    is_consumable: bool = False  # Whether this transport consumes an item

    @property
    def has_requirements(self) -> bool:
        """Check if this transport has any requirements."""
        return bool(
            self.skill_requirements
            or self.quest_requirements
            or self.item_requirements
            or self.varbit_requirements
            or self.varplayer_requirements
            or self.max_wilderness_level >= 0
        )

    @property
    def requirements_summary(self) -> str:
        """Get a human-readable summary of requirements."""
        parts = []

        if self.skill_requirements:
            skills = [
                f"{skill} {level}" for skill, level in sorted(self.skill_requirements.items())
            ]
            parts.append(f"Skills: {', '.join(skills)}")

        if self.quest_requirements:
            quests = sorted(self.quest_requirements)
            if len(quests) <= 3:
                parts.append(f"Quests: {', '.join(quests)}")
            else:
                parts.append(f"Quests: {', '.join(quests[:3])}... (+{len(quests) - 3} more)")

        if self.item_requirements:
            parts.append(f"Items: {len(self.item_requirements)} required")

        if self.max_wilderness_level >= 0:
            parts.append(f"Max Wildy: {self.max_wilderness_level}")

        if self.varbit_requirements:
            varbit_strs = []
            for vid, val, op in self.varbit_requirements:
                varbit_strs.append(f"{vid}{op}{val}")
            parts.append(f"Varbits: {', '.join(varbit_strs)}")

        if self.varplayer_requirements:
            vp_strs = []
            for vid, val, op in self.varplayer_requirements:
                vp_strs.append(f"{vid}{op}{val}")
            parts.append(f"VarPlayers: {', '.join(vp_strs)}")

        return " | ".join(parts) if parts else "None"

    @property
    def location_str(self) -> str:
        """Get location as string."""
        return f"({self.x}, {self.y}, {self.plane})"

    @property
    def origin_str(self) -> str | None:
        """Get origin location as string, or None if no origin."""
        if self.origin_x is not None:
            return f"({self.origin_x}, {self.origin_y}, {self.origin_plane})"
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "node_id": self.node_id,
            "transport_id": self.transport_id,
            "name": self.name,
            "transport_type": self.transport_type,
            "x": self.x,
            "y": self.y,
            "plane": self.plane,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "origin_plane": self.origin_plane,
            "is_spawn_point": self.is_spawn_point,
            "activation_cost": self.activation_cost,
            "duration_ticks": self.duration_ticks,
            "skill_requirements": self.skill_requirements,
            "quest_requirements": self.quest_requirements,
            "item_requirements": self.item_requirements,
            "varbit_requirements": self.varbit_requirements,
            "varplayer_requirements": self.varplayer_requirements,
            "max_wilderness_level": self.max_wilderness_level,
            "display_info": self.display_info,
            "action": self.action,
            "is_consumable": self.is_consumable,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TransportMetadata:
        """Create from dictionary."""
        return cls(
            node_id=data["node_id"],
            transport_id=data["transport_id"],
            name=data["name"],
            transport_type=data["transport_type"],
            x=data["x"],
            y=data["y"],
            plane=data["plane"],
            origin_x=data.get("origin_x"),
            origin_y=data.get("origin_y"),
            origin_plane=data.get("origin_plane"),
            is_spawn_point=data.get("is_spawn_point", False),
            activation_cost=data.get("activation_cost", 0),
            duration_ticks=data.get("duration_ticks", 0),
            skill_requirements=data.get("skill_requirements", {}),
            quest_requirements=data.get("quest_requirements", []),
            item_requirements=data.get("item_requirements", []),
            varbit_requirements=data.get("varbit_requirements", []),
            varplayer_requirements=data.get("varplayer_requirements", []),
            max_wilderness_level=data.get("max_wilderness_level", -1),
            display_info=data.get("display_info", ""),
            action=data.get("action", ""),
            is_consumable=data.get("is_consumable", False),
        )


class TransportMetadataDB:
    """Database of transport metadata, keyed by node ID.

    Each node ID maps to a list of TransportMetadata entries.
    Spawn nodes may have multiple entries (one per transport variant).
    Non-spawn nodes typically have one entry.
    """

    def __init__(self, metadata: dict[int, list[TransportMetadata]] | None = None):
        """Initialize with optional metadata dict."""
        self._metadata: dict[int, list[TransportMetadata]] = metadata or {}

    def __len__(self) -> int:
        """Return number of node entries."""
        return len(self._metadata)

    def get(self, node_id: int) -> list[TransportMetadata] | None:
        """Get metadata list for a node ID, or None if not found."""
        return self._metadata.get(node_id)

    def add(self, metadata: TransportMetadata) -> None:
        """Add metadata entry (appends to existing list for the node)."""
        if metadata.node_id not in self._metadata:
            self._metadata[metadata.node_id] = []
        self._metadata[metadata.node_id].append(metadata)

    def get_by_type(self, transport_type: str) -> list[TransportMetadata]:
        """Get all metadata entries of a specific transport type."""
        return [
            m
            for entries in self._metadata.values()
            for m in entries
            if m.transport_type == transport_type
        ]

    def get_spawn_points(self) -> list[TransportMetadata]:
        """Get all spawn point metadata (first entry per spawn node)."""
        return [entries[0] for entries in self._metadata.values() if entries[0].is_spawn_point]

    def get_by_location(self, x: int, y: int, plane: int) -> list[TransportMetadata] | None:
        """Get metadata by location (slower O(n) lookup)."""
        for entries in self._metadata.values():
            if entries and entries[0].x == x and entries[0].y == y and entries[0].plane == plane:
                return entries
        return None

    def save(self, path: Path) -> None:
        """Save database to pickle file."""
        data = {
            "version": 2,
            "metadata": {
                k: [m.to_dict() for m in entries] for k, entries in self._metadata.items()
            },
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)

    @classmethod
    def load(cls, path: Path) -> TransportMetadataDB:
        """Load database from pickle file."""
        with open(path, "rb") as f:
            data = pickle.load(f)

        version = data.get("version", 0)
        if version == 1:
            # Migrate v1 (single metadata per node) to v2 (list per node)
            metadata = {
                int(k): [TransportMetadata.from_dict(v)] for k, v in data["metadata"].items()
            }
        elif version == 2:
            metadata = {
                int(k): [TransportMetadata.from_dict(m) for m in entries]
                for k, entries in data["metadata"].items()
            }
        else:
            raise ValueError(f"Unknown metadata version: {version}")

        return cls(metadata)

    @classmethod
    def from_file(cls, path: str | Path) -> TransportMetadataDB:
        """Load from file path (convenience method)."""
        return cls.load(Path(path))

    def stats(self) -> dict[str, int | dict[str, int]]:
        """Get statistics about the database."""
        all_meta = [m for entries in self._metadata.values() for m in entries]
        stats: dict[str, int | dict[str, int]] = {
            "total_nodes": len(self._metadata),
            "total_entries": len(all_meta),
            "spawn_points": sum(
                1 for entries in self._metadata.values() if entries[0].is_spawn_point
            ),
            "with_requirements": sum(1 for m in all_meta if m.has_requirements),
        }

        # Count by type
        type_counts: dict[str, int] = {}
        for meta in all_meta:
            type_counts[meta.transport_type] = type_counts.get(meta.transport_type, 0) + 1
        stats["by_type"] = type_counts

        return stats
