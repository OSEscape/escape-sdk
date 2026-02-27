"""Escape - OSRS Bot Development SDK.

A Python SDK for Old School RuneScape bot development with an intuitive
structure that mirrors the game's interface.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path as _Path
from typing import TYPE_CHECKING

__version__ = "2.2.1"
__author__ = "Escape Team"

# Ensure generated files path is available for imports
_proto_path = str(_Path(__file__).parent / "_proto")
if _proto_path not in sys.path:
    sys.path.insert(0, _proto_path)

from escape.client import Client

if TYPE_CHECKING:
    from escape._models import EntityType, Item, ItemIdentifier, Skill
    from escape.equipment import EquipmentSlots
    from escape.gametab import GameTab, GameTabs
    from escape.geometry import Box, Circle, Polygon, Quad, Shape
    from escape.interaction import hover, interact, right_click
    from escape.npcs import Npc
    from escape.objects import SceneObject
    from escape.pathfinder import Path, PathfinderConfig, Transport
    from escape.point import Point, Point3D, ScreenPoint
    from escape.prayer import PrayerType
    from escape.tile_items import GroundItem
    from escape.timing import sleep, wait_until

__all__ = [
    "Box",
    "Circle",
    "Client",
    "EntityType",
    "EquipmentSlots",
    "GameTab",
    "GameTabs",
    "GroundItem",
    "Item",
    "ItemIdentifier",
    "Npc",
    "Path",
    "PathfinderConfig",
    "Point",
    "Point3D",
    "Polygon",
    "PrayerType",
    "Quad",
    "SceneObject",
    "ScreenPoint",
    "Shape",
    "Skill",
    "Transport",
    "hover",
    "interact",
    "right_click",
    "sleep",
    "wait_until",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "EntityType": ("escape._models", "EntityType"),
    "Npc": ("escape.npcs", "Npc"),
    "SceneObject": ("escape.objects", "SceneObject"),
    "GroundItem": ("escape.tile_items", "GroundItem"),
    "Item": ("escape._models", "Item"),
    "ItemIdentifier": ("escape._models", "ItemIdentifier"),
    "Point": ("escape.point", "Point"),
    "Point3D": ("escape.point", "Point3D"),
    "ScreenPoint": ("escape.point", "ScreenPoint"),
    "Box": ("escape.geometry", "Box"),
    "Circle": ("escape.geometry", "Circle"),
    "Polygon": ("escape.geometry", "Polygon"),
    "Quad": ("escape.geometry", "Quad"),
    "Shape": ("escape.geometry", "Shape"),
    "wait_until": ("escape.timing", "wait_until"),
    "sleep": ("escape.timing", "sleep"),
    "Path": ("escape.pathfinder", "Path"),
    "PathfinderConfig": ("escape.pathfinder", "PathfinderConfig"),
    "Transport": ("escape.pathfinder", "Transport"),
    "Skill": ("escape._models", "Skill"),
    "EquipmentSlots": ("escape.equipment", "EquipmentSlots"),
    "GameTab": ("escape.gametab", "GameTab"),
    "GameTabs": ("escape.gametab", "GameTabs"),
    "PrayerType": ("escape.prayer", "PrayerType"),
    "hover": ("escape.interaction", "hover"),
    "interact": ("escape.interaction", "interact"),
    "right_click": ("escape.interaction", "right_click"),
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
