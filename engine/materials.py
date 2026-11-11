"""Materiales y estimacion de metraje.

Las agujas por grosor y los factores de metraje son **ASUNCIONES** de trabajo:
se basan en rangos habituales, no en una tabla publicada verificada. Se
documentan en `docs/fuentes.md` y el patron siempre advierte que el metraje es
una estimacion.
"""

from __future__ import annotations

from engine.spec import YarnWeight

# Agujas y ganchillos: tamano dentro del rango recomendado por el Craft Yarn
# Council (Standard Yarn Weight System, verificado 2026-11-11), cerca del
# punto medio y redondeado a un tamano comercial.
# Agujas CYC: lace 1.5-2.25, super fine 2.25-3.25, fine 3.25-3.75,
# light 3.75-4.5, medium 4.5-5.5, bulky 5.5-8, super bulky 8-12.75 mm.
NEEDLE_MM_BY_WEIGHT: dict[YarnWeight, float] = {
    YarnWeight.LACE: 2.0,
    YarnWeight.FINGERING: 2.75,
    YarnWeight.SPORT: 3.5,
    YarnWeight.DK: 4.0,
    YarnWeight.WORSTED: 5.0,
    YarnWeight.BULKY: 6.5,
    YarnWeight.SUPER_BULKY: 10.0,
    YarnWeight.UNKNOWN: 4.0,
}

# Ganchillos CYC: lace 2.25 (regular), super fine 2.25-3.5, fine 3.5-4.5,
# light 4.5-5.5, medium 5.5-6.5, bulky 6.5-9, super bulky 9-15 mm.
HOOK_MM_BY_WEIGHT: dict[YarnWeight, float] = {
    YarnWeight.LACE: 2.25,
    YarnWeight.FINGERING: 3.0,
    YarnWeight.SPORT: 4.0,
    YarnWeight.DK: 5.0,
    YarnWeight.WORSTED: 6.0,
    YarnWeight.BULKY: 8.0,
    YarnWeight.SUPER_BULKY: 12.0,
    YarnWeight.UNKNOWN: 5.0,
}

# Metros de hilo por cm2 de tejido, con margen incluido aparte.
# ASUNCION: valores medios para punto jersey; el calado y las trenzas consumen
# mas hilo.
METERS_PER_CM2: dict[YarnWeight, float] = {
    YarnWeight.LACE: 0.18,
    YarnWeight.FINGERING: 0.12,
    YarnWeight.SPORT: 0.10,
    YarnWeight.DK: 0.08,
    YarnWeight.WORSTED: 0.07,
    YarnWeight.BULKY: 0.05,
    YarnWeight.SUPER_BULKY: 0.035,
    YarnWeight.UNKNOWN: 0.08,
}

# Metros por cada 100 g, para estimar los gramos a partir del metraje.
METERS_PER_100G: dict[YarnWeight, float] = {
    YarnWeight.LACE: 400.0,
    YarnWeight.FINGERING: 350.0,
    YarnWeight.SPORT: 300.0,
    YarnWeight.DK: 250.0,
    YarnWeight.WORSTED: 200.0,
    YarnWeight.BULKY: 125.0,
    YarnWeight.SUPER_BULKY: 80.0,
    YarnWeight.UNKNOWN: 250.0,
}

DEFAULT_MARGIN = 1.15


def default_needle_mm(weight: YarnWeight) -> float:
    return NEEDLE_MM_BY_WEIGHT[weight]


def default_hook_mm(weight: YarnWeight) -> float:
    return HOOK_MM_BY_WEIGHT[weight]


def estimate_yarn(
    area_cm2: float,
    weight: YarnWeight,
    *,
    margin: float = DEFAULT_MARGIN,
) -> tuple[float, float | None]:
    """Devuelve (metros, gramos) redondeados, con margen de seguridad."""
    if area_cm2 < 0:
        raise ValueError("el area no puede ser negativa")
    meters = area_cm2 * METERS_PER_CM2[weight] * margin
    meters = float(round(meters / 10.0) * 10)
    grams = meters / (METERS_PER_100G[weight] / 100.0)
    return meters, float(round(grams))
