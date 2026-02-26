"""OSRS Game Resources System.

Provides access to game data (varps, varbits, objects) loaded at initialization.
Data is downloaded and loaded once per session by cache_manager.ensureResourcesLoaded().
"""

from escape._resources import objects as objects
from escape._resources import questdata as questdata
from escape._resources import varps as varps

__all__ = [
    "objects",
    "questdata",
    "varps",
]
