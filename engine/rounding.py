"""Redondeos explicitos y deterministicos.

Python usa redondeo bancario en `round()`, que no es lo que espera una
persona tejedora. Aca todo redondeo es "half up" y esta documentado.
"""

from __future__ import annotations

import math


def round_half_up(value: float) -> int:
    """Redondea al entero mas cercano, con .5 hacia arriba."""
    if not math.isfinite(value):
        raise ValueError(f"valor no finito: {value!r}")
    return math.floor(value + 0.5)


def clamp(value: int, low: int, high: int) -> int:
    """Limita un entero al rango [low, high]."""
    if low > high:
        raise ValueError("rango invalido")
    return max(low, min(high, value))
