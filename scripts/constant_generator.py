"""Generate Python constants from RuneLite gameval Java files."""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

from loguru import logger

# GitHub configuration
GITHUB_RAW = "https://raw.githubusercontent.com/runelite/runelite/master/runelite-api/src/main/java/net/runelite/api/gameval"
GITHUB_API = "https://api.github.com/repos/runelite/runelite/commits?path=runelite-api/src/main/java/net/runelite/api/gameval&per_page=1"

# File configurations
FILES = {
    "AnimationID": {"nested": False, "hex": False},
    "DBTableID": {"nested": False, "hex": False},
    "InterfaceID": {"nested": True, "hex": True},
    "InventoryID": {"nested": False, "hex": False},
    "ItemID": {"nested": True, "hex": False},
    "NpcID": {"nested": False, "hex": False},
    "ObjectID": {"nested": False, "hex": False, "merge_with": "ObjectID1"},
    # ObjectID1 is merged into ObjectID (ObjectID extends ObjectID1 in Java)
    "SpotanimID": {"nested": False, "hex": False},
    "SpriteID": {"nested": True, "hex": False},
    "VarClientID": {"nested": False, "hex": False},
    "VarPlayerID": {"nested": False, "hex": False},
    "VarbitID": {"nested": False, "hex": False},
}


def get_latest_commit() -> str | None:
    """Get latest commit SHA for the gameval directory."""
    try:
        req = urllib.request.Request(GITHUB_API, headers={"User-Agent": "escape-codegen/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data[0]["sha"] if data else None
    except Exception:
        return None


def fetch_java_file(filename: str) -> str:
    """Fetch Java constant file from GitHub."""
    url = f"{GITHUB_RAW}/{filename}.java"
    req = urllib.request.Request(url, headers={"User-Agent": "escape-codegen/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


def parse_simple_constants(content: str, allow_hex: bool = False) -> dict[str, int]:
    """Parse simple constants from Java file content."""
    if allow_hex:
        pattern = r"public\s+static\s+final\s+int\s+([A-Z_0-9]+)\s*=\s*([0-9-]+|0x[0-9a-fA-F_]+);"
    else:
        pattern = r"public\s+static\s+final\s+int\s+([A-Z_0-9]+)\s*=\s*([0-9-]+);"

    constants = {}
    for match in re.finditer(pattern, content):
        name, value = match.groups()
        if value.startswith("0x"):
            # Remove underscores from hex values (Java numeric literal separators)
            value = value.replace("_", "")
            constants[name] = int(value, 16)
        else:
            constants[name] = int(value)
    return constants


def detect_nested_classes(content: str) -> list[str]:
    """Detect all nested class declarations."""
    pattern = r"public\s+static\s+(?:final\s+)?class\s+([A-Z_][A-Za-z0-9_]*)\s*\{"
    return [match.group(1) for match in re.finditer(pattern, content)]


def remove_nested_classes(content: str) -> str:
    """Remove all nested class definitions from content."""
    # Find all nested class blocks and remove them
    result = content

    # Keep removing nested classes until none remain
    # Use a simple approach: find each nested class and remove it
    while True:
        # Find nested class declaration
        match = re.search(
            r"public\s+static\s+(?:final\s+)?class\s+([A-Z_][A-Za-z0-9_]*)\s*\{", result
        )
        if not match:
            break

        # Find matching closing brace
        start = match.start()
        brace_start = match.end()
        brace_count = 1
        pos = brace_start

        while pos < len(result) and brace_count > 0:
            if result[pos] == "{":
                brace_count += 1
            elif result[pos] == "}":
                brace_count -= 1
            pos += 1

        # Remove the entire nested class
        if brace_count == 0:
            result = result[:start] + result[pos:]
        else:
            break  # Malformed, stop

    return result


def extract_class_body(content: str, class_name: str) -> str | None:
    """Extract the body of a nested class by matching braces."""
    # Find the class declaration
    class_pattern = rf"public\s+static\s+(?:final\s+)?class\s+{class_name}\s*\{{"
    match = re.search(class_pattern, content)
    if not match:
        return None

    # Start after the opening brace
    start = match.end()
    brace_count = 1
    pos = start

    # Match braces to find the end of the class
    while pos < len(content) and brace_count > 0:
        if content[pos] == "{":
            brace_count += 1
        elif content[pos] == "}":
            brace_count -= 1
        pos += 1

    if brace_count != 0:
        return None

    return content[start : pos - 1]


def parse_nested_class(content: str, class_name: str, allow_hex: bool = False) -> dict[str, int]:
    """Parse constants from a specific nested class."""
    class_body = extract_class_body(content, class_name)
    if not class_body:
        return {}

    return parse_simple_constants(class_body, allow_hex=allow_hex)


def generate_class(
    name: str,
    constants: dict[str, int],
    nested_classes: dict[str, dict[str, int]],
    format_hex: bool = False,
) -> str:
    """Generate Python class with constants and nested classes."""
    lines = [f'"""Auto-generated {name} constants from RuneLite (gameval)."""']
    lines.append("")
    lines.append(f"class {name}:")

    # Generate top-level constants
    if constants:
        for const_name, value in sorted(constants.items()):
            if format_hex:
                lines.append(f"    {const_name} = 0x{value:08X}")
            else:
                lines.append(f"    {const_name} = {value}")

        # Add blank line after top-level constants if there are nested classes
        if nested_classes:
            lines.append("")
    elif not nested_classes:
        # Empty class
        lines.append("    pass")

    # Generate nested classes
    for nested_name in sorted(nested_classes.keys()):
        nested_consts = nested_classes[nested_name]
        lines.append(f"    class {nested_name}:")

        if not nested_consts:
            lines.append("        pass")
        else:
            for const_name, value in sorted(nested_consts.items()):
                if format_hex:
                    lines.append(f"        {const_name} = 0x{value:08X}")
                else:
                    lines.append(f"        {const_name} = {value}")

        lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Generate constants from RuneLite gameval."""
    parser = argparse.ArgumentParser(description="Generate constants from RuneLite gameval")
    parser.add_argument(
        "--force", action="store_true", help="Force regeneration even if up to date"
    )
    args = parser.parse_args()

    constants_dir = Path(__file__).parent.parent / "escape" / "constants"
    version_file = constants_dir / ".version"

    # Create constants directory if it doesn't exist
    constants_dir.mkdir(exist_ok=True)

    # Check if update needed
    latest_commit = get_latest_commit()
    if not args.force and version_file.exists() and latest_commit:
        current_version = version_file.read_text().strip()
        if current_version == latest_commit:
            logger.info(f"Constants already up to date ({latest_commit[:8]})")
            return 0

    logger.info("Fetching RuneLite constants from gameval...")

    generated_modules = []

    for filename, config in sorted(FILES.items()):
        try:
            content = fetch_java_file(filename)

            # Parse nested classes first if applicable
            nested_classes = {}
            if config["nested"]:
                for nested_name in detect_nested_classes(content):
                    nested_classes[nested_name] = parse_nested_class(
                        content, nested_name, allow_hex=config["hex"]
                    )

            # Parse top-level constants (remove nested classes first to avoid duplicates)
            top_level_content = remove_nested_classes(content) if config["nested"] else content
            constants = parse_simple_constants(top_level_content, allow_hex=config["hex"])

            # Handle merge_with for ObjectID (which extends ObjectID1 in Java)
            if "merge_with" in config:
                merge_file = config["merge_with"]
                merge_content = fetch_java_file(merge_file)
                merge_constants = parse_simple_constants(merge_content, allow_hex=config["hex"])
                # Merge: ObjectID1 constants come first (base class), then ObjectID constants
                constants = {**merge_constants, **constants}

            # Generate Python class
            class_code = generate_class(
                filename, constants, nested_classes, format_hex=config["hex"]
            )

            # Write to separate file
            module_name = f"_{filename.lower()}"
            output_file = constants_dir / f"{module_name}.py"

            file_lines = ['"""Auto-generated constants from RuneLite gameval."""']
            file_lines.append("")
            file_lines.append("# This file is auto-generated by constant_generator.py")
            file_lines.append("# Do not edit manually - changes will be overwritten")
            if "merge_with" in config:
                file_lines.append(
                    f"# Note: Merged with {config['merge_with']} ({filename} extends {config['merge_with']} in Java)"
                )
            file_lines.append("")
            file_lines.append(class_code)

            output_file.write_text("\n".join(file_lines) + "\n")

            generated_modules.append((module_name, filename))

            const_count = len(constants)
            nested_count = sum(len(nc) for nc in nested_classes.values())
            total = const_count + nested_count
            merge_note = f" (merged with {config['merge_with']})" if "merge_with" in config else ""
            logger.info(
                f"  {filename}: {total} constants ({len(nested_classes)} nested classes){merge_note}"
            )

        except Exception as e:
            logger.error(f"  {filename}: {e}")
            return 1

    # Generate __init__.py
    init_lines = ['"""RuneLite constant classes."""']
    init_lines.append("")
    init_lines.append("# Auto-generated by constant_generator.py")
    init_lines.append("")

    # Sort imports alphabetically by module name for ruff compliance
    sorted_modules = sorted(generated_modules, key=lambda x: x[0])

    for module_name, class_name in sorted_modules:
        init_lines.append(f"from .{module_name} import {class_name}")

    init_lines.append("")
    init_lines.append("__all__ = [")
    # Sort __all__ alphabetically by class name (not module name)
    sorted_classes = sorted([class_name for _, class_name in sorted_modules])
    for class_name in sorted_classes:
        init_lines.append(f'    "{class_name}",')
    init_lines.append("]")
    init_lines.append("")  # Add trailing newline

    init_file = constants_dir / "__init__.py"
    init_file.write_text("\n".join(init_lines))

    # Save version
    if latest_commit:
        version_file.write_text(latest_commit)

    logger.info(f"Generated {len(generated_modules)} files in {constants_dir}")
    logger.info(f"Version: {latest_commit[:8] if latest_commit else 'unknown'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
