"""Familias de prendas. Cada familia es una funcion pura `generate`."""

from __future__ import annotations

from engine.garments.base import (
    GarmentError,
    ImpossibleProportionsError,
    UnsupportedGarmentError,
)
from engine.garments.flat import generate_flat
from engine.garments.raglan import generate_raglan_top_down
from engine.garments.set_in import generate_set_in
from engine.garments.yoke import generate_yoke
from engine.ir import Pattern
from engine.spec import Category, Construction, GarmentSpec, PatternParams, Technique


def generate(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Despacha la familia soportada. Falla claro si no hay familia."""
    if spec.tecnica not in {Technique.NEEDLES, Technique.CIRCULAR}:
        raise UnsupportedGarmentError(
            "error.unsupported_technique", technique=spec.tecnica.value
        )
    if spec.categoria is Category.CARDIGAN:
        return generate_flat(spec, params, "cardigan")
    if spec.categoria is Category.VEST:
        return generate_flat(spec, params, "vest")
    if spec.categoria is Category.PULLOVER:
        construction = spec.construccion or Construction.RAGLAN_TOP_DOWN
        if construction is Construction.RAGLAN_TOP_DOWN:
            return generate_raglan_top_down(spec, params)
        if construction is Construction.DROP_SHOULDER:
            return generate_flat(spec, params, "drop_shoulder")
        if construction is Construction.YOKE:
            return generate_yoke(spec, params)
        if construction is Construction.SET_IN_SLEEVE:
            return generate_set_in(spec, params)
    raise UnsupportedGarmentError(
        "error.unsupported_garment",
        category=spec.categoria.value,
        construction=(spec.construccion or Construction.OTHER).value,
    )


__all__ = [
    "GarmentError",
    "ImpossibleProportionsError",
    "UnsupportedGarmentError",
    "generate",
    "generate_flat",
    "generate_raglan_top_down",
    "generate_set_in",
    "generate_yoke",
]
