"""Resource loader for game data from ~/.cache/escape/data/game_data/."""

import json
import os
import sqlite3
from pathlib import Path

from escape._logger import logger

# Track if resources have been loaded this session
_resources_loaded = False


def get_game_data_dir() -> Path:
    """Get path to game data cache directory.

    Returns ~/.cache/escape/data/game_data/ (or $XDG_CACHE_HOME/escape/data/game_data/)
    """
    xdg_cache = os.getenv("XDG_CACHE_HOME")
    base_path = Path(xdg_cache) / "escape" if xdg_cache else Path.home() / ".cache" / "escape"
    return base_path / "data" / "game_data"


def ensure_resources_loaded() -> bool:
    """Load game resources from cache into memory.

    Resources must be pre-downloaded using resource_generator.py.
    Run: python escape/resource_generator.py
    """
    global _resources_loaded

    if _resources_loaded:
        return True

    try:
        cache_dir = get_game_data_dir()

        # Check if required files exist
        required_files = ["metadata.json", "varps.json", "varbits.json", "objects.db"]
        required_dirs = ["graph"]

        missing = []
        for f in required_files:
            if not (cache_dir / f).exists():
                missing.append(f)
        for d in required_dirs:
            if not (cache_dir / d).is_dir():
                missing.append(f"{d}/")

        if missing:
            logger.error(f"Required resources not found: {', '.join(missing)}")
            logger.error("Run: python escape/resource_generator.py")
            return False

        # Load resources into modules
        from escape._resources import objects, varps

        # Load varps/varbits data
        varps_file = cache_dir / "varps.json"
        varbits_file = cache_dir / "varbits.json"

        with open(varps_file) as f:
            raw_varps = json.load(f)
            # Convert list to dict indexed by ID
            if isinstance(raw_varps, list):
                varps_data = {item["id"]: item for item in raw_varps if "id" in item}
            else:
                varps_data = raw_varps
            varps.set_varps_data(varps_data)
            logger.success(f"Loaded {varps.get_varps_data_count()} varps")

        with open(varbits_file) as f:
            raw_varbits = json.load(f)
            # Convert list to dict indexed by ID
            if isinstance(raw_varbits, list):
                varbits_data = {item["id"]: item for item in raw_varbits if "id" in item}
            else:
                varbits_data = raw_varbits
            varps.set_varbits_data(varbits_data)
            logger.success(f"Loaded {varps.get_varbits_data_count()} varbits")

        # Load objects database
        db_file = cache_dir / "objects.db"
        db_conn = sqlite3.connect(str(db_file))
        objects.set_db_connection(db_conn)
        logger.success("Loaded objects database")

        _resources_loaded = True
        return True

    except Exception as e:
        logger.error(f"Failed to load resources: {e}")
        import traceback

        traceback.print_exc()
        return False
