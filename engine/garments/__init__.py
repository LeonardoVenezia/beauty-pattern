"""Familias de prendas. Cada familia es una funcion pura `generate`."""

from __future__ import annotations

from engine.garments.base import (
    GarmentError,
    ImpossibleProportionsError,
    UnsupportedGarmentError,
)
from engine.garments.raglan import generate_raglan_top_down
from engine.ir import Pattern
from engine.spec import Category, Construction, GarmentSpec, PatternParams, Technique


def generate(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Despacha la familia soportada. Falla claro si no hay familia."""
    if spec.categoria is not Category.PULLOVER:
        raise UnsupportedGarmentError(
            "error.unsupported_garment",
            category=spec.categoria.value,
            construction=(spec.construccion or Construction.OTHER).value,
        )
    if spec.tecnica not in {Technique.NEEDLES, Technique.CIRCULAR}:
        raise UnsupportedGarmentError(
            "error.unsupported_technique", technique=spec.tecnica.value
        )
    if spec.construccion not in {None, Construction.RAGLAN_TOP_DOWN}:
        raise UnsupportedGarmentError(
            "error.unsupported_garment",
            category=spec.categoria.value,
            construction=spec.construccion.value,
        )
    return generate_raglan_top_down(spec, params)


__all__ = [
    "GarmentError",
    "ImpossibleProportionsError",
    "UnsupportedGarmentError",
    "generate",
    "generate_raglan_top_down",
]
