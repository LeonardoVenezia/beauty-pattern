"""Tablas de medidas corporales y holguras.

Fuente de los rangos de talle: Craft Yarn Council, "Standard Body
Measurements". Los valores usados son puntos medios redondeados de esos
rangos. Las holguras por ajuste y los largos son ASUNCIONES de este motor:
estan documentados en docs/fuentes.md y deben editarse si la prenda real
difiere.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.spec import Fit


@dataclass(frozen=True)
class BodySize:
    key: str
    bust_cm: float
    waist_cm: float
    hip_cm: float
    body_length_cm: float
    sleeve_length_cm: float
    upper_arm_cm: float
    neck_cm: float
    cross_back_cm: float
    armhole_cm: float = 21.0
    wrist_cm: float = 17.0


# Medidas en cm. `body_length_cm` es de nuca a cadera; `sleeve_length_cm` de
# hombro a muneca. ASUNCION: valores intermedios para tejido con holgura.
BODY_SIZES: dict[str, BodySize] = {
    "XS": BodySize("XS", 74, 58, 84, 54, 56, 26, 35, 36, 19, 15),
    "S": BodySize("S", 84, 68, 92, 56, 57, 28, 36, 38, 20, 16),
    "M": BodySize("M", 94, 76, 100, 58, 58, 30, 37, 40, 21, 16.5),
    "L": BodySize("L", 104, 84, 108, 60, 59, 32, 38, 42, 22, 17),
    "XL": BodySize("XL", 114, 92, 116, 62, 60, 34, 39, 44, 23, 18),
    "2XL": BodySize("2XL", 124, 100, 124, 63, 61, 37, 40, 46, 24, 19),
    "3XL": BodySize("3XL", 134, 108, 132, 64, 62, 40, 41, 48, 25, 20),
}

# Holgura positiva por ajuste (cm sobre el contorno del cuerpo).
# ASUNCION basada en convenciones habituales de patronaje de punto.
EASE_BY_FIT: dict[Fit, float] = {
    Fit.FITTED: -2.0,
    Fit.REGULAR: 6.0,
    Fit.LOOSE: 12.0,
    Fit.VERY_LOOSE: 20.0,
    Fit.OVERSIZED: 25.0,  # ASUNCION: oversize de patrones actuales, 20-30 cm
}

MEASUREMENT_KEYS = (
    "bust",
    "waist",
    "hip",
    "body_length",
    "sleeve_length",
    "upper_arm",
    "neck",
    "cross_back",
    "armhole",
    "wrist",
)


def ease_for_fit(fit: Fit | None) -> float:
    return EASE_BY_FIT[fit or Fit.REGULAR]


def resolve_body_size(
    size_key: str, overrides_cm: dict[str, float] | None = None
) -> BodySize:
    """Devuelve la fila de talle con las medidas propias que la reemplacen."""
    key = size_key.strip().upper()
    if key not in BODY_SIZES:
        valid = ", ".join(BODY_SIZES)
        raise ValueError(f"talle desconocido {size_key!r}; talles: {valid}")
    base = BODY_SIZES[key]
    overrides = overrides_cm or {}
    unknown = set(overrides) - set(MEASUREMENT_KEYS)
    if unknown:
        raise ValueError(f"medidas desconocidas: {', '.join(sorted(unknown))}")
    return BodySize(
        key=base.key,
        bust_cm=overrides.get("bust", base.bust_cm),
        waist_cm=overrides.get("waist", base.waist_cm),
        hip_cm=overrides.get("hip", base.hip_cm),
        body_length_cm=overrides.get("body_length", base.body_length_cm),
        sleeve_length_cm=overrides.get("sleeve_length", base.sleeve_length_cm),
        upper_arm_cm=overrides.get("upper_arm", base.upper_arm_cm),
        neck_cm=overrides.get("neck", base.neck_cm),
        cross_back_cm=overrides.get("cross_back", base.cross_back_cm),
        armhole_cm=overrides.get("armhole", base.armhole_cm),
        wrist_cm=overrides.get("wrist", base.wrist_cm),
    )
