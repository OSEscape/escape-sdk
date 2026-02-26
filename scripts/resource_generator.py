"""Generate game resources from os-escape.com data server."""

import argparse
import gzip
import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from loguru import logger

# Data server configuration
BASE_URL = "https://data.os-escape.com/resources"
GRAPH_URL = f"{BASE_URL}/graph_data.zip"

# File configurations
FILES = {
    "metadata.json": {"compressed": False},
    "varps.json": {"compressed": False},
    "varbits.json": {"compressed": False},
    "objects.db.gz": {"compressed": True, "dest": "objects.db"},
}


def get_cache_dir() -> Path:
    """Get the cache directory for game data."""
    xdg_cache = os.getenv("XDG_CACHE_HOME")
    base_path = Path(xdg_cache) / "escape" if xdg_cache else Path.home() / ".cache" / "escape"

    cache_dir = base_path / "data" / "game_data"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_remote_version() -> str | None:
    """Fetch remote metadata to get current version/revision."""
    url = f"{BASE_URL}/metadata.json"

    try:
        req = urllib.request.Request(_bust_cache(url), headers={
            "User-Agent": "escape-resource-gen/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("updated_at")
    except Exception:
        return None


def _bust_cache(url: str) -> str:
    """Append a cache-busting query parameter to a URL."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}_t={int(time.time())}"


def download_file(url: str, dest: Path) -> bool:
    """Download a file from URL to destination."""
    try:
        req = urllib.request.Request(_bust_cache(url), headers={
            "User-Agent": "escape-resource-gen/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()

        with open(dest, "wb") as f:
            f.write(data)

        return True

    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return False


def decompress_gz(gz_path: Path, dest: Path) -> bool:
    """Decompress a gzip file."""
    try:
        with gzip.open(gz_path, "rb") as f_in, open(dest, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        # Remove .gz file after successful decompression
        gz_path.unlink()
        return True

    except Exception as e:
        logger.error(f"Failed to decompress {gz_path}: {e}")
        return False


def download_and_extract_zip(url: str, extract_dir: Path) -> bool:
    """Download a zip file and extract it to a directory."""
    try:
        # Download zip
        req = urllib.request.Request(_bust_cache(url), headers={
            "User-Agent": "escape-resource-gen/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()

        # Write to temp file
        temp_zip = extract_dir.parent / "temp_download.zip"
        with open(temp_zip, "wb") as f:
            f.write(data)

        # Clear existing directory if it exists
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)

        # Extract
        with zipfile.ZipFile(temp_zip, "r") as zf:
            zf.extractall(extract_dir)

        # Clean up temp file
        temp_zip.unlink()
        return True

    except Exception as e:
        logger.error(f"Failed to download/extract {url}: {e}")
        return False


def main() -> int:
    """Generate game resources from data server."""
    parser = argparse.ArgumentParser(description="Generate game resources from data server")
    parser.add_argument("--force", action="store_true", help="Force download even if up to date")
    args = parser.parse_args()

    cache_dir = get_cache_dir()
    version_file = cache_dir / ".version"

    # Check if update needed
    remote_version = get_remote_version()
    if not args.force and version_file.exists() and remote_version:
        current_version = version_file.read_text().strip()
        if current_version == remote_version:
            logger.info(f"Resources already up to date (version: {remote_version})")
            return 0

    logger.info("Downloading game resources from data.os-escape.com...")

    # Download standard files
    for filename, config in FILES.items():
        url = f"{BASE_URL}/{filename}"

        if config["compressed"]:
            gz_path = cache_dir / filename

            if not download_file(url, gz_path):
                return 1

            dest_path = cache_dir / config["dest"]

            if not decompress_gz(gz_path, dest_path):
                return 1

            logger.info(f"  {filename}: {dest_path.stat().st_size:,} bytes")
        else:
            dest_path = cache_dir / filename

            if not download_file(url, dest_path):
                return 1

            logger.info(f"  {filename}: {dest_path.stat().st_size:,} bytes")

    # Download and extract graph data
    graph_dir = cache_dir / "graph"

    if not download_and_extract_zip(GRAPH_URL, graph_dir):
        return 1

    file_count = len(list(graph_dir.rglob("*")))
    logger.info(f"  graph_data.zip: {file_count} files extracted")

    # Download quests.py to source tree
    quests_url = f"{BASE_URL}/quests.py"
    quests_dest = Path(__file__).resolve().parent.parent / "escape" / "_resources" / "questdata.py"

    if not download_file(quests_url, quests_dest):
        return 1

    logger.info(f"  quests.py: {quests_dest.stat().st_size:,} bytes -> {quests_dest}")

    # Save version
    if remote_version:
        version_file.write_text(remote_version)

    logger.info(f"Resources downloaded to {cache_dir}")
    logger.info(f"Version: {remote_version or 'unknown'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
