"""Centralized logging configuration for escape SDK."""

import sys
from typing import TYPE_CHECKING

from loguru import logger as _logger

if TYPE_CHECKING:
    from loguru import Logger

# Remove default handler to reconfigure
_logger.remove()

# Configure console output with colors and formatting
# Format: timestamp | level | module:function:line - message
_logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG",
    colorize=True,
    backtrace=True,
    diagnose=True,
)

# Export configured logger
logger: Logger = _logger


def set_level(level: str) -> None:
    """Set the global logging level."""
    _logger.remove()
    _logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level.upper(),
        colorize=True,
        backtrace=True,
        diagnose=True,
    )


def enable_file_logging(path: str, level: str = "DEBUG", rotation: str = "10 MB") -> None:
    """Enable logging to a file in addition to console."""
    _logger.add(
        path,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level=level.upper(),
        rotation=rotation,
        compression="gz",
        serialize=False,  # Set to True for JSON logging
    )


def enable_json_logging(path: str, level: str = "DEBUG", rotation: str = "10 MB") -> None:
    """Enable JSON structured logging to a file (for log aggregators)."""
    _logger.add(
        path,
        level=level.upper(),
        rotation=rotation,
        compression="gz",
        serialize=True,  # JSON output
    )


__all__ = ["enable_file_logging", "enable_json_logging", "logger", "set_level"]
