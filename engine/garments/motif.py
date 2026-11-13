"""Motivos radiales de crochet (mandala, carpeta, cuadrado con centro redondo).

Capa de diseno: la IA describe la estructura que ve con vocabulario cerrado
(`MotifDesign`: forma, simetria, bandas de punto y color, del centro hacia
afuera). Aca se calcula todo lo numerico para la medida pedida:

- vueltas por banda: el grosor relativo de cada banda se escala para que el
  radio (o medio lado) llegue a la medida;
- puntos por vuelta: un circulo plano necesita 2 pi x radio / ancho de punto;
  se redondea a un multiplo de la simetria para que cada vuelta sea "S veces
  la misma secuencia" (asi se ven los petalos);
- vueltas caladas (red, piña/popcorn, cluster, puff): grupos separados por
  1 cad; donde la vuelta crece, el grupo no salta punto;
- cuadrado: una vuelta de esquinas (pad en la esquina, pts mas bajos hacia el
  centro del lado) y despues vueltas con esquinas de 2 cad.

ASUNCION: altos relativos de pad (0,40 del pb de referencia) y de puff; ver
docs/fuentes.md. El simulador verifica el conteo de cada vuelta.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from engine.distribution import split_even
from engine.garments.base import ImpossibleProportionsError
from engine.gauge import crochet_gauge
from engine.i18n import t
from engine.ir import Item, Measurement, Op, Pattern, Repeat, Section, Step, Warning, build_step
from engine.spec import GarmentSpec, MotifDesign, MotifShape, MotifStitch, PatternParams
from engine.stitches.kinds import StitchKind

# (ancho, alto) de un punto relativos al pb de referencia (engine/gauge.py).
_SHAPE: dict[MotifStitch, tuple[float, float]] = {
    MotifStitch.SC: (1.0, 1.1),
    MotifStitch.HDC: (0.95, 0.75),
    MotifStitch.DC: (0.9, 0.55),
    MotifStitch.TR: (0.9, 0.40),
    MotifStitch.MESH: (0.9, 0.55),
    MotifStitch.CLUSTER: (0.9, 0.55),
    MotifStitch.POPCORN: (0.9, 0.55),
    MotifStitch.PUFF: (0.9, 0.65),
}
_SOLID: dict[MotifStitch, StitchKind] = {
    MotifStitch.SC: StitchKind.SC,
    MotifStitch.HDC: StitchKind.HDC,
    MotifStitch.DC: StitchKind.DC,
    MotifStitch.TR: StitchKind.TR,
}
_SPACED: dict[MotifStitch, StitchKind] = {
    MotifStitch.MESH: StitchKind.DC,
    MotifStitch.CLUSTER: StitchKind.CLUSTER,
    MotifStitch.POPCORN: StitchKind.POPCORN,
    MotifStitch.PUFF: StitchKind.PUFF,
}


@dataclass(frozen=True)
class _Round:
    band: int
    stitch: MotifStitch
    square: bool


def _sizes(sc_per_cm: float, stitch: MotifStitch) -> tuple[float, float]:
    """(ancho de un punto, alto de una vuelta) en cm."""
    width, height = _SHAPE[stitch]
    return 1.0 / (sc_per_cm * width), 1.0 / (sc_per_cm * height)


def natural_size_cm(design: MotifDesign, sc_per_cm: float) -> float:
    """Medida sin pedido de la usuaria: la banda mas fina con 1 vuelta y las
    demas en proporcion, como en la foto. Asi el default depende del motivo y
    del hilo, no de un numero fijo."""
    thinnest = min(band.peso for band in design.bandas)
    return 2 * sum(band.peso / thinnest * _sizes(sc_per_cm, band.punto)[1] for band in design.bandas)


def _rounds_per_band(design: MotifDesign, radius: float, sc_per_cm: float) -> list[int]:
    """Vueltas de cada banda: el grosor relativo escalado al radio pedido y
    despues ajustado de a una vuelta (sin bajar de 1 por banda)."""
    heights = [_sizes(sc_per_cm, band.punto)[1] for band in design.bandas]
    weights = [band.peso for band in design.bandas]
    k = radius / sum(w * h for w, h in zip(weights, heights, strict=True))
    counts = [max(1, round(k * w)) for w in weights]

    def error(values: list[int]) -> float:
        return abs(sum(n * h for n, h in zip(values, heights, strict=True)) - radius)

    while True:
        options = [
            [n + (delta if i == j else 0) for j, n in enumerate(counts)]
            for i in range(len(counts))
            for delta in (1, -1)
            if counts[i] + delta >= 1
        ]
        best = min(options, key=error, default=counts)
        if error(best) >= error(counts) - 1e-9:
            return counts
        counts = best


def _square_band(design: MotifDesign) -> int | None:
    if design.forma is not MotifShape.SQUARE:
        return None
    if design.cuadrar_en_banda is not None:
        return min(design.cuadrar_en_banda, len(design.bandas) - 1)
    return min(len(design.bandas) - 1, max(0, round(0.6 * len(design.bandas))))


def _spaced_sector(previous: int, target: int, feature: StitchKind) -> list[Op]:
    """Sector calado: `a` grupos (pt, 1 cad, saltar 1) y `b` grupos (pt, 1 cad)
    sin saltar, repartidos. Consume `previous`, produce `target` (par)."""
    b = target - previous
    a = (2 * previous - target) // 2
    units: list[list[Op]] = []
    spread = set()
    if b:
        gaps = split_even(a, b) if a else [0] * b
        position = 0
        for gap in gaps:
            position += gap
            spread.add(position)
            position += 1
    for index in range(a + b):
        unit = [Op(feature), Op(StitchKind.CH)]
        if index not in spread:
            unit.append(Op(StitchKind.SKIP))
        units.append(unit)
    return [op for unit in units for op in unit]


def _solid_sector(previous: int, target: int, kind: StitchKind) -> list[Op]:
    increases = target - previous
    if increases == 0:
        return [Op(kind, times=previous)]
    ops: list[Op] = []
    for group in split_even(previous - increases, increases):
        if group:
            ops.append(Op(kind, times=group))
        ops.append(Op(StitchKind.CROCHET_INC))
    return ops


def _graded_side(stitches: int) -> list[Op]:
    """Lado de la vuelta que cuadra: pts mas altos junto a las esquinas."""
    if stitches <= 0:
        return []
    if stitches < 7:
        return [Op(StitchKind.DC, times=stitches)]
    tr = dc = hdc = max(1, round(stitches * 0.12))
    sc = stitches - 2 * (tr + dc + hdc)
    kinds = [(StitchKind.TR, tr), (StitchKind.DC, dc), (StitchKind.HDC, hdc), (StitchKind.SC, sc),
             (StitchKind.HDC, hdc), (StitchKind.DC, dc), (StitchKind.TR, tr)]
    return [Op(kind, times=n) for kind, n in kinds if n]


def _sector_items(ops: list[Op], sectors: int) -> tuple[Item, ...]:
    return (Repeat(sectors, tuple(ops)),)


def _note(design: MotifDesign, band: int, lang: str, colors: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    spec_band = design.bandas[band]
    color = ""
    if spec_band.color is not None:
        letter = chr(65 + spec_band.color)
        name = colors[spec_band.color] if spec_band.color < len(colors) else ""
        color = t("pattern.motif_color", lang, letter=letter, name=f" ({name})" if name else "")
    return (
        ("band", str(band + 1)),
        ("stitch", t(f"motif.stitch.{spec_band.punto.value}", lang)),
        ("color", color),
    )


def _multiple(rounds: list[_Round], index: int, sectors: int) -> int:
    """Multiplo de puntos de una vuelta redonda: la simetria (x2 si es calada,
    por los grupos de pt + cad) y multiplo de 4 si la siguiente cuadra."""
    rnd = rounds[index]
    if rnd.square:
        return 4
    multiple = sectors * (2 if rnd.stitch in _SPACED else 1)
    if index + 1 < len(rounds) and rounds[index + 1].square:
        multiple = math.lcm(multiple, 4)
    return multiple


def motif_steps(
    design: MotifDesign, size_cm: float, sc_per_cm: float, lang: str, colors: tuple[str, ...] = ()
) -> tuple[tuple[Step, ...], float, list[str]]:
    """(vueltas, medida real en cm, simplificaciones)."""
    counts = _rounds_per_band(design, size_cm / 2, sc_per_cm)
    square_from = _square_band(design)
    rounds = [
        _Round(band, design.bandas[band].punto, square_from is not None and band >= square_from)
        for band, n in enumerate(counts)
        for _ in range(n)
    ]
    if rounds[0].square:  # la vuelta 1 (anillo) siempre es redonda
        rounds[0] = _Round(rounds[0].band, rounds[0].stitch, False)
    sectors = design.simetria
    steps: list[Step] = []
    simplified: list[str] = []
    radius = 0.0
    previous = 0
    corner = (0, 0)  # pts antes y despues de las 2 cad de esquina, por lado
    for index, rnd in enumerate(rounds):
        width, height = _sizes(sc_per_cm, rnd.stitch)
        radius += height
        squaring = rnd.square and not rounds[index - 1].square
        first_of_band = index == 0 or rounds[index - 1].band != rnd.band
        note_key: str | None = None
        params: tuple[tuple[str, str], ...] = ()
        if first_of_band or squaring:
            note_key = "pattern.note.motif_squaring" if squaring else "pattern.note.motif_band"
            if index == 0 and rnd.stitch in _SPACED:
                note_key = "pattern.note.motif_ring_spaced"
            params = _note(design, rnd.band, lang, colors)
            if rnd.square and rnd.stitch not in _SOLID:  # en la parte cuadrada los calados van en pa
                params = tuple((k, t("motif.stitch.dc", lang) if k == "stitch" else v) for k, v in params)
        spaced = rnd.stitch in _SPACED
        if not rnd.square:
            multiple = _multiple(rounds, index, sectors)
            # Que la vuelta siguiente pueda llegar a su multiplo sin pasar de
            # duplicar los puntos.
            following = _multiple(rounds, index + 1, sectors) if index + 1 < len(rounds) else 1
            floor_next = math.ceil(following / 2 / multiple) * multiple
            ideal = 2 * math.pi * radius / width
            if index == 0:
                target = max(floor_next, multiple * max(1, round(ideal / multiple)), 3)
                items: tuple[Item, ...] = (Op(StitchKind.RING, width=target),)
            else:
                low = max(math.ceil(previous / multiple) * multiple, floor_next)
                high = (2 * previous // multiple) * multiple
                if high < low:
                    raise ImpossibleProportionsError("error.motif_symmetry", symmetry=sectors)
                target = min(high, max(low, multiple * round(ideal / multiple)))
                per, new = previous // sectors, target // sectors
                ops = (
                    _spaced_sector(per, new, _SPACED[rnd.stitch])
                    if spaced
                    else _solid_sector(per, new, _SOLID[rnd.stitch])
                )
                items = _sector_items(ops, sectors)
        elif squaring:
            side = previous // 4 - 1
            items = _sector_items([Op(StitchKind.SQUARE_TURN), *_graded_side(side)], 4)
            corner = (2, 2 + side)
            target = previous + 4 * 5
        else:
            kind = _SOLID.get(rnd.stitch)
            if kind is None:
                kind = StitchKind.DC
                if rnd.stitch.value not in simplified:
                    simplified.append(rnd.stitch.value)
            corner_kind, grow = (StitchKind.CORNER_SC, 1) if kind is StitchKind.SC else (StitchKind.CORNER_DC, 2)
            before, after = corner
            items = _sector_items([Op(kind, times=before), Op(corner_kind), Op(kind, times=after)], 4)
            corner = (before + grow, after + grow)
            target = previous + 4 * 2 * grow
        step = build_step(index + 1, previous, items, note_key=note_key, note_params=params)
        if step.stitch_count_end != target:
            raise RuntimeError(f"motivo: vuelta {index + 1} da {step.stitch_count_end}, se esperaban {target}")
        steps.append(step)
        previous = target
    return tuple(steps), 2 * radius, simplified


def generate_crochet_motif(spec: GarmentSpec, params: PatternParams) -> Pattern:
    from engine.garments.crochet import _materials, _meta, _warnings

    design = spec.motivo
    if design is None:
        raise ValueError("generate_crochet_motif requiere spec.motivo")
    if params.densidad is None:  # la muestra del documento va en pb, no la de dos agujas
        params = params.model_copy(update={"densidad": crochet_gauge(params.peso_hilo.value, "crochet_sc")})
    assert params.densidad is not None
    sc_per_cm = params.densidad.stitches_per_cm  # muestra medida en pb
    size = params.dimensiones_cm.get("size", params.medidas_cm.get("size", natural_size_cm(design, sc_per_cm)))
    colors = tuple(spec.colorwork.paleta) if spec.colorwork else ()
    steps, actual, simplified = motif_steps(design, size, sc_per_cm, params.idioma, colors)
    tallest = max(_sizes(sc_per_cm, band.punto)[1] for band in design.bandas)
    tolerance = max(1.5, 2 * tallest)
    # Solo pasa si ni con 1 vuelta por banda entra en la medida pedida.
    resized = abs(actual - size) > tolerance
    square = design.forma is MotifShape.SQUARE
    key = "width" if square else "diameter"
    section = Section(
        id="motif",
        name_key="section.motif",
        mode="round",
        steps=steps,
        start_stitches=0,
        end_stitches=steps[-1].stitch_count_end,
        meta={"row_count": len(steps), "symmetry": design.simetria},
        bind_off=True,
        note_keys=("pattern.motif_intro",),
    )
    warnings = [w for w in _warnings(params) if w.code != "crochet_gauge"]
    warnings.append(
        Warning(
            "motif_design",
            "warning.motif_design",
            severity="info",
            params={"bands": len(design.bandas), "symmetry": design.simetria},
        )
    )
    if resized:
        warnings.append(
            Warning(
                "motif_resized",
                "warning.motif_resized",
                params={"actual": round(actual), "asked": round(size), "weight": params.peso_hilo.value},
            )
        )
    if simplified:
        warnings.append(Warning("motif_square_simplified", "warning.motif_square_simplified"))
    if len(colors) > 1:
        letters = ", ".join(f"{chr(65 + i)} ({c})" for i, c in enumerate(colors))
        warnings.append(Warning("motif_colors", "warning.motif_colors", severity="info", params={"colors": letters}))
    area = actual * actual if square else math.pi * (actual / 2) ** 2
    return Pattern(
        meta=_meta(spec, params, "crochet_motif", "title.crochet_motif"),
        spec=spec,
        params=params,
        sections=(section,),
        measurements=(
            Measurement(key=key, value_cm=actual, target_cm=actual if resized else size, tolerance_cm=tolerance, kind="width"),
        ),
        materials=_materials(spec, params, area, ("notion.crochet_hook", "notion.tapestry_needle", "notion.stitch_markers")),
        warnings=tuple(warnings),
    )
