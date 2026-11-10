"""Deteccion de repeticion para convertir un motivo en un ancho repetible."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class RepeatPattern:
    period_x: int
    period_y: int
    confidence_x: float
    confidence_y: float


@dataclass(frozen=True)
class MotifFit:
    width: int
    repeats: int


def _period_score(gray: np.ndarray, period: int, axis: int) -> float:
    if axis == 0:
        if period >= gray.shape[1]:
            return 0.0
        diff = np.abs(gray[:, :-period] - gray[:, period:])
    else:
        if period >= gray.shape[0]:
            return 0.0
        diff = np.abs(gray[:-period, :] - gray[period:, :])
    return float(1.0 - diff.mean() / 255.0)


def _best_period(
    gray: np.ndarray, axis: int, min_period: int, max_period: int
) -> tuple[int, float]:
    best_period = 1
    best_score = 0.0
    for period in range(max(1, min_period), max_period + 1):
        score = _period_score(gray, period, axis)
        if score > best_score:
            best_period = period
            best_score = score
    return best_period, max(0.0, min(1.0, best_score))


def detect_repeat(
    image: Image.Image,
    *,
    min_period: int = 4,
    max_period: int | None = None,
) -> RepeatPattern:
    """Busca el periodo horizontal y vertical por autocorrelacion simple."""
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    height, width = gray.shape
    limit_x = max_period or max(min_period, width // 3)
    limit_y = max_period or max(min_period, height // 3)
    period_x, confidence_x = _best_period(gray, 0, min_period, min(limit_x, width - 1))
    period_y, confidence_y = _best_period(gray, 1, min_period, min(limit_y, height - 1))
    return RepeatPattern(period_x, period_y, confidence_x, confidence_y)


def fit_motif_width(stitches: int, motif_width: int) -> MotifFit:
    """Ajusta el ancho del motivo a un divisor del total de puntos."""
    if stitches < 1 or motif_width < 1:
        raise ValueError("stitches y motif_width deben ser >= 1")
    divisors = [d for d in range(1, stitches + 1) if stitches % d == 0]
    chosen = min(divisors, key=lambda d: (abs(d - motif_width), d))
    return MotifFit(width=chosen, repeats=stitches // chosen)
