import math


def _chebyshev(ex: int, ey: int, px: int, py: int) -> int:
    return max(abs(ex - px), abs(ey - py))


def _combat_level(
    attack: int,
    strength: int,
    defence: int,
    hitpoints: int,
    prayer: int,
    ranged: int,
    magic: int,
) -> int:
    base = 0.25 * (defence + hitpoints + math.floor(prayer / 2))
    melee = 13 / 40 * (attack + strength)
    range_ = 13 / 40 * math.floor(ranged * 3 / 2)
    mage = 13 / 40 * math.floor(magic * 3 / 2)
    return math.floor(base + max(melee, range_, mage))
