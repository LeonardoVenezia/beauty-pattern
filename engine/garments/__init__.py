"""Familias de prendas. Cada familia es una funcion pura `generate`."""

from __future__ import annotations

from dataclasses import replace

from engine.garments.accessories import (
    generate_bag,
    generate_blanket,
    generate_cowl,
    generate_flat_piece,
    generate_hat,
    generate_mittens,
    generate_scarf,
    generate_shawl,
    generate_socks,
)
from engine.garments.base import (
    GarmentError,
    ImpossibleProportionsError,
    UnsupportedGarmentError,
)
from engine.garments.crochet import (
    generate_amigurumi,
    generate_crochet_bag,
    generate_crochet_cowl,
    generate_crochet_flat_piece,
    generate_crochet_garment,
    generate_crochet_hat,
    generate_crochet_scarf,
    generate_crochet_shawl,
    generate_granny_square,
)
from engine.garments.flat import generate_flat
from engine.garments.raglan import generate_raglan_top_down
from engine.garments.routing import route
from engine.garments.set_in import generate_set_in
from engine.garments.yoke import generate_yoke
from engine.ir import Pattern, Warning
from engine.spec import (
    Category,
    ColorworkType,
    Construction,
    GarmentSpec,
    PatternParams,
    StitchPatternName,
    Technique,
    Texture,
)


def generate(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Patron de la familia soportada mas cercana a lo que se vio.

    `route` lleva cualquier combinacion de categoria y tecnica a una familia
    verificada; lo que se aproximo o no se pudo reproducir queda en las
    advertencias del patron (nunca se pierde en silencio).
    """
    routed, notes = route(spec)
    pattern = _generate(routed, params)
    extra = [Warning(f"approx_{note}", f"warning.approx.{note}") for note in notes]
    codes = {w.code for w in pattern.warnings}
    seen_other = spec.punto_base is StitchPatternName.OTHER or any(
        obs.textura is Texture.OTHER for obs in spec.texturas
    )
    if seen_other and "texture_panel" not in codes:
        extra.append(Warning("texture_unidentified", "warning.texture_unidentified"))
    if (
        spec.colorwork is not None
        and spec.colorwork.tipo not in {ColorworkType.NONE, ColorworkType.STRIPES}
        and "colorwork_not_charted" not in codes
    ):
        extra.append(Warning("colorwork_not_charted", "warning.colorwork_generic"))
    if not extra:
        return pattern
    return replace(pattern, warnings=(*pattern.warnings, *extra))


def _generate(spec: GarmentSpec, params: PatternParams) -> Pattern:
    if spec.tecnica is Technique.CROCHET:
        if spec.categoria is Category.AMIGURUMI:
            return generate_amigurumi(spec, params)
        if spec.categoria is Category.SCARF:
            return generate_crochet_scarf(spec, params)
        if spec.categoria in {Category.BLANKET, Category.GRANNY_SQUARE}:
            return generate_granny_square(spec, params)
        if spec.categoria is Category.BAG:
            return generate_crochet_bag(spec, params)
        if spec.categoria is Category.HAT:
            return generate_crochet_hat(spec, params)
        if spec.categoria is Category.COWL:
            return generate_crochet_cowl(spec, params)
        if spec.categoria is Category.SHAWL:
            return generate_crochet_shawl(spec, params)
        if spec.categoria in {Category.PULLOVER, Category.CARDIGAN, Category.VEST}:
            return generate_crochet_garment(spec, params, spec.categoria.value)
        if spec.categoria is Category.OTHER:
            return generate_crochet_flat_piece(spec, params)
        raise UnsupportedGarmentError(
            "error.unsupported_technique", technique=spec.tecnica.value
        )
    if spec.tecnica not in {Technique.NEEDLES, Technique.CIRCULAR}:
        raise UnsupportedGarmentError(
            "error.unsupported_technique", technique=spec.tecnica.value
        )
    if spec.categoria is Category.HAT:
        return generate_hat(spec, params)
    if spec.categoria is Category.SCARF:
        return generate_scarf(spec, params)
    if spec.categoria is Category.COWL:
        return generate_cowl(spec, params)
    if spec.categoria is Category.MITTENS:
        return generate_mittens(spec, params)
    if spec.categoria is Category.SOCKS:
        return generate_socks(spec, params)
    if spec.categoria is Category.SHAWL:
        return generate_shawl(spec, params)
    if spec.categoria is Category.BLANKET:
        return generate_blanket(spec, params)
    if spec.categoria is Category.BAG:
        return generate_bag(spec, params)
    if spec.categoria is Category.OTHER:
        return generate_flat_piece(spec, params)
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
    "generate_amigurumi",
    "generate_bag",
    "generate_blanket",
    "generate_cowl",
    "generate_crochet_bag",
    "generate_crochet_flat_piece",
    "generate_crochet_scarf",
    "generate_flat",
    "generate_flat_piece",
    "generate_granny_square",
    "generate_hat",
    "generate_mittens",
    "generate_raglan_top_down",
    "generate_scarf",
    "generate_set_in",
    "generate_shawl",
    "generate_socks",
    "generate_yoke",
]


_SIZED = {Category.PULLOVER, Category.CARDIGAN, Category.VEST}


def generate_size_set(spec: GarmentSpec, params: PatternParams) -> list[Pattern]:
    """Un patron verificado por talle de la tabla (o uno solo si no aplica).

    Prendas con talle y sin medidas propias: todos los talles de la tabla,
    cada uno pasado por el simulador. Un talle que no cierra se omite (nunca
    se entrega sin verificar); si ninguno cierra, falla como `generate`.
    Accesorios, crochet y medidas propias: un solo patron.
    """
    from engine.simulator import simulate
    from engine.sizes import BODY_SIZES

    if spec.categoria not in _SIZED or params.medidas_cm:
        return [generate(spec, params)]
    patterns: list[Pattern] = []
    error: GarmentError | None = None
    for size in BODY_SIZES:
        try:
            pattern = generate(spec, params.model_copy(update={"talla": size}))
        except GarmentError as exc:
            error = exc
            continue
        if simulate(pattern).ok:
            patterns.append(pattern)
    if not patterns:
        if error is not None:
            raise error
        raise UnsupportedGarmentError("error.pattern_failed_verification")
    return patterns
