"""Varps and Varbits accessor functions.

Use with constant IDs from escape.constants:
    from escape._resources import varps
    from escape.constants import VarbitID, VarPlayerID

    varps.get_varbit(VarbitID.BANK_CURRENTTAB)
"""

from typing import Any

from escape._logger import logger

__all__ = [
    "extract_bits",
    "get_varbit",
    "get_varbit_info",
    "get_varbits_data_count",
    "get_varc_name",
    "get_varps_data_count",
    "set_varbits_data",
    "set_varps_data",
]

# Module-level data (loaded by cache_manager at init)
_varps_data: dict[int, dict[str, Any]] | None = None
_varbits_data: dict[int, dict[str, Any]] | None = None


def extract_bits(value: int, start_bit: int, end_bit: int) -> int:
    num_bits = end_bit - start_bit + 1
    mask = (1 << num_bits) - 1
    return (value >> start_bit) & mask


def get_varbit_info(varbit_id: int) -> dict[str, Any] | None:
    if not _varbits_data:
        return None

    varbit_info = _varbits_data.get(varbit_id)
    if not varbit_info:
        return None

    return {
        "varp": varbit_info.get("varp"),
        "lsb": varbit_info.get("lsb", 0),
        "msb": varbit_info.get("msb", 31),
        "name": varbit_info.get("name", f"varbit_{varbit_id}"),
    }


def get_varp_value(varp_id: int) -> int | None:
    from escape._services import Services

    return Services.get().cache.get_varp(varp_id)


def get_varbit(varbit_id: int) -> int | None:
    from escape._services import Services

    if not _varbits_data:
        logger.error("Varbits data not loaded")
        return None

    varbit_info = _varbits_data.get(varbit_id)
    if not varbit_info:
        logger.error(f"Varbit {varbit_id} not found in metadata")
        return None

    varp_id = varbit_info.get("varp")
    if varp_id is None:
        logger.error(f"Varbit {varbit_id} has no varp mapping")
        return None

    varp_value = Services.get().cache.get_varp(varp_id)
    if varp_value is None:
        return None

    start_bit = varbit_info.get("lsb", 0)
    end_bit = varbit_info.get("msb", 31)

    return extract_bits(varp_value, start_bit, end_bit)


# Cache for VarClientID id -> name mapping (built on first use)
_varc_id_to_name: dict[int, str] | None = None


def _build_varc_cache() -> dict[int, str]:
    global _varc_id_to_name

    if _varc_id_to_name is not None:
        return _varc_id_to_name

    _varc_id_to_name = {}
    try:
        from escape.constants import VarClientID  # pyright: ignore[reportMissingImports]

        for name, value in vars(VarClientID).items():
            if not name.startswith("_") and isinstance(value, int):
                _varc_id_to_name[value] = name
    except ImportError:
        pass

    return _varc_id_to_name


def get_varc_name(varc_id: int) -> str | None:
    return _build_varc_cache().get(varc_id)


# Setter functions for cache_manager
def set_varps_data(data: dict[int, dict[str, Any]]) -> None:
    global _varps_data
    _varps_data = data


def set_varbits_data(data: dict[int, dict[str, Any]]) -> None:
    global _varbits_data
    _varbits_data = data


def get_varps_data_count() -> int:
    return len(_varps_data) if _varps_data else 0


def get_varbits_data_count() -> int:
    return len(_varbits_data) if _varbits_data else 0
