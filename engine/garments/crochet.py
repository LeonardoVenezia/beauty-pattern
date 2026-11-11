"""Crochet: amigurumi y piezas planas.

Las formas de amigurumi se generan con anillo magico y aumentos/disminuciones
de 6 puntos por vuelta. El granny square es el clasico en redondo (grupos de
3 pa y esquinas de 2 cad); no reproduce motivos complejos de la foto y lo
declara en una advertencia.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from math import pi

from engine import ENGINE_VERSION
from engine.distribution import split_even
from engine.garments.base import ImpossibleProportionsError
from engine.gauge import crochet_gauge
from engine.ir import (
    Materials,
    Measurement,
    Op,
    Pattern,
    PatternMeta,
    Repeat,
    Section,
    SectionTarget,
    Step,
    Warning,
    build_step,
)
from engine.materials import default_hook_mm, estimate_yarn
from engine.rounding import round_half_up
from engine.spec import (
    GarmentSpec,
    PatternParams,
    Shape,
    StitchPatternName,
    Technique,
    resolve_gauge,
)
from engine.stitches.catalog import adjust_stitches, catalog_id_for_name, expand_row, get_stitch
from engine.stitches.kinds import StitchKind

_CROCHET_IDS = {"crochet_sc", "crochet_hdc", "crochet_dc"}
_KIND_BY_ID = {
    "crochet_sc": StitchKind.SC,
    "crochet_hdc": StitchKind.HDC,
    "crochet_dc": StitchKind.DC,
}


def _pattern_id(spec: GarmentSpec) -> str:
    pattern_id = catalog_id_for_name(spec.punto_base or StitchPatternName.CROCHET_SC)
    return pattern_id if pattern_id in _CROCHET_IDS else "crochet_sc"


def _with_crochet_gauge(spec: GarmentSpec, params: PatternParams) -> PatternParams:
    """Si no hay muestra medida, fija la referencia de crochet del punto base.

    Sin esto el motor usaba la densidad de dos agujas (22 x 30 en DK): 46
    hileras de pa daban "15 cm" cuando en realidad miden ~40 cm.
    """
    if params.densidad is not None:
        return params
    gauge = crochet_gauge(params.peso_hilo.value, _pattern_id(spec))
    return params.model_copy(update={"densidad": gauge})


def _kind(pattern_id: str) -> StitchKind:
    return _KIND_BY_ID[pattern_id]


def _meta(spec: GarmentSpec, params: PatternParams, family: str, title_key: str) -> PatternMeta:
    digest = hashlib.sha256(
        (spec.model_dump_json() + params.model_dump_json() + family).encode("utf-8")
    ).hexdigest()[:12]
    return PatternMeta(
        id=digest,
        family=family,
        title_key=title_key,
        size=params.talla,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        engine_version=ENGINE_VERSION,
    )


def _materials(
    spec: GarmentSpec,
    params: PatternParams,
    area_cm2: float,
    notions: tuple[str, ...],
) -> Materials:
    meters, grams = estimate_yarn(area_cm2, params.peso_hilo)
    colors = tuple(spec.colorwork.paleta) if spec.colorwork else ()
    return Materials(
        yarn_weight=params.peso_hilo,
        needle_mm=None,
        hook_mm=params.ganchillo_mm or default_hook_mm(params.peso_hilo),
        meters=meters,
        grams=grams,
        notions=notions,
        colors=colors,
    )


def _warnings(params: PatternParams) -> list[Warning]:
    warnings = [
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", "warning.assumption", severity="info"),
        Warning("crochet_gauge", "warning.crochet_gauge", severity="info"),
    ]
    if params.medidas_cm:
        warnings.append(
            Warning("custom_measurements", "warning.custom_measurements", severity="info")
        )
    return warnings


def _increase_round(
    stitches: int, increases: int, kind: StitchKind
) -> tuple[list[Op], int]:
    if increases < 0:
        raise ValueError("increases no puede ser negativo")
    if increases == 0:
        return ([Op(kind, times=stitches)] if stitches else []), stitches
    if stitches <= 0:
        raise ValueError("se necesitan puntos para aumentar")
    remaining = stitches - increases
    if remaining < 0:
        raise ValueError(
            f"no se pueden hacer {increases} aumentos en {stitches} puntos"
        )
    groups = split_even(remaining, increases)
    ops: list[Op] = []
    for group in groups:
        if group:
            ops.append(Op(kind, times=group))
        ops.append(Op(StitchKind.CROCHET_INC))
    return ops, stitches + increases


def _decrease_round(
    stitches: int, decreases: int, kind: StitchKind
) -> tuple[list[Op], int]:
    if decreases < 0:
        raise ValueError("decreases no puede ser negativo")
    if decreases == 0:
        return ([Op(kind, times=stitches)] if stitches else []), stitches
    if decreases * 2 > stitches:
        raise ValueError(
            f"no se pueden hacer {decreases} disminuciones en {stitches} puntos"
        )
    remaining = stitches - 2 * decreases
    groups = split_even(remaining, decreases)
    ops: list[Op] = []
    for group in groups:
        if group:
            ops.append(Op(kind, times=group))
        ops.append(Op(StitchKind.CROCHET_DEC))
    return ops, stitches - decreases


def _amigurumi_shape(spec: GarmentSpec) -> str:
    if spec.forma is Shape.BOXY:
        return "cylinder"
    if spec.forma in {Shape.A_LINE, Shape.CURVED}:
        return "cone"
    return "sphere"


def generate_amigurumi(spec: GarmentSpec, params: PatternParams) -> Pattern:
    params = _with_crochet_gauge(spec, params)
    if spec.tecnica is not Technique.CROCHET:
        raise ImpossibleProportionsError(
            "error.unsupported_technique", technique=spec.tecnica.value
        )
    gauge = resolve_gauge(params)
    diameter = params.dimensiones_cm.get("diameter", params.medidas_cm.get("diameter", 8.0))
    height = params.dimensiones_cm.get("height", params.medidas_cm.get("height", diameter))
    shape = _amigurumi_shape(spec)
    base_circumference = pi * diameter
    target = adjust_stitches(
        max(6, round_half_up(base_circumference * gauge.stitches_per_cm)),
        6,
        mode="nearest",
    )
    if abs(gauge.cm_for_stitches(target) - base_circumference) > 0.1 * base_circumference:
        raise ImpossibleProportionsError(
            "error.too_small_for_yarn",
            weight=params.peso_hilo.value,
            target=round(diameter, 1),
        )
    increase_rounds = (target - 6) // 6
    height_rows = max(1, gauge.rows_for_cm(height))
    if shape == "sphere":
        decrease_rounds = increase_rounds
        straight_rows = max(0, height_rows - increase_rounds - decrease_rounds)
    elif shape == "cylinder":
        decrease_rounds = 0
        straight_rows = max(1, height_rows - increase_rounds)
    else:
        decrease_rounds = 0
        straight_rows = max(0, height_rows - increase_rounds)

    pattern_id = _pattern_id(spec)
    kind = _kind(pattern_id)
    steps: list[Step] = [
        build_step(1, 0, (Op(StitchKind.MAGIC_RING),))
    ]
    current = 6
    number = 2
    for _ in range(increase_rounds):
        before = current
        items, current = _increase_round(current, 6, kind)
        steps.append(
            build_step(number, before, items, note_key="pattern.note.amigurumi_increase")
        )
        number += 1
    for _ in range(straight_rows):
        steps.append(
            build_step(number, current, (Op(kind, times=current),), note_key="pattern.note.plain")
        )
        number += 1
    for _ in range(decrease_rounds):
        items, current = _decrease_round(current, 6, kind)
        steps.append(
            build_step(number, current + 6, items, note_key="pattern.note.amigurumi_decrease")
        )
        number += 1
    if shape == "sphere" and current != 6:
        raise RuntimeError(f"amigurumi: termina con {current} puntos, se esperaban 6")

    total_rows = len(steps)
    actual_height = gauge.cm_for_rows(total_rows)
    if abs(actual_height - height) > 1.5:
        raise ImpossibleProportionsError(
            "error.too_small_for_yarn",
            weight=params.peso_hilo.value,
            target=round(height, 1),
        )
    target_circumference = gauge.cm_for_stitches(target)
    actual_diameter = target_circumference / pi
    section = Section(
        id="amigurumi",
        name_key="section.amigurumi",
        mode="round",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=current,
        target=(
            None
            if shape == "sphere"
            else SectionTarget(
                measurement_key="circumference",
                target_cm=base_circumference,
                tolerance_cm=2.5,
                dimension="circumference",
            )
        ),
        meta={"row_count": total_rows, "base_stitches": target},
        bind_off=True,
    )
    area = (
        4.0 * pi * (diameter / 2.0) ** 2
        if shape == "sphere"
        else pi * diameter * height
    )
    warnings = _warnings(params)
    warnings.append(
        Warning("amigurumi_approx", "warning.amigurumi_approx", severity="warning")
    )
    return Pattern(
        meta=_meta(spec, params, "amigurumi", "title.amigurumi"),
        spec=spec,
        params=params,
        sections=(section,),
        measurements=(
            Measurement(
                key="diameter",
                value_cm=actual_diameter,
                target_cm=diameter,
                tolerance_cm=1.5,
                kind="circumference",
            ),
            Measurement(
                key="height",
                value_cm=actual_height,
                target_cm=height,
                tolerance_cm=1.5,
                kind="length",
            ),
        ),
        materials=_materials(
            spec,
            params,
            area,
            ("notion.crochet_hook", "notion.stitch_markers", "notion.tapestry_needle"),
        ),
        warnings=tuple(warnings),
    )


def _flat_section(
    section_id: str,
    name_key: str,
    stitches: int,
    rows: int,
    pattern_id: str,
    target_cm: float,
    *,
    note_key: str,
) -> Section:
    pattern = get_stitch(pattern_id)
    steps: list[Step] = [
        build_step(
            1,
            0,
            (Op(StitchKind.CH, times=stitches),),
            note_key="pattern.note.crochet_foundation",
        )
    ]
    for number in range(2, rows + 2):
        steps.append(
            build_step(
                number,
                stitches,
                expand_row(pattern, stitches, number - 1),
                note_key=note_key if number == 2 else None,
            )
        )
    return Section(
        id=section_id,
        name_key=name_key,
        mode="flat",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=stitches,
        target=SectionTarget(
            measurement_key=f"{section_id}_length",
            target_cm=target_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": rows, "cast_on": stitches},
        bind_off=True,
    )


def _flat_pattern(
    spec: GarmentSpec,
    params: PatternParams,
    *,
    family: str,
    title_key: str,
    section_id: str,
    section_key: str,
    width: float,
    length: float,
    warning: Warning | None = None,
) -> Pattern:
    params = _with_crochet_gauge(spec, params)
    gauge = resolve_gauge(params)
    pattern_id = _pattern_id(spec)
    multiple = get_stitch(pattern_id).multiple
    stitches = adjust_stitches(
        max(1, round_half_up(width * gauge.stitches_per_cm)), multiple, mode="nearest"
    )
    rows = max(1, gauge.rows_for_cm(length))
    section = _flat_section(
        section_id,
        section_key,
        stitches,
        rows,
        pattern_id,
        length,
        note_key="pattern.note.crochet_flat",
    )
    warnings = _warnings(params)
    if warning is not None:
        warnings.append(warning)
    return Pattern(
        meta=_meta(spec, params, family, title_key),
        spec=spec,
        params=params,
        sections=(section,),
        measurements=(
            Measurement(
                key="width",
                value_cm=gauge.cm_for_stitches(stitches),
                target_cm=width,
                tolerance_cm=1.5,
                kind="width",
            ),
            Measurement(
                key="length",
                value_cm=gauge.cm_for_rows(rows),
                target_cm=length,
                tolerance_cm=1.5,
                kind="length",
            ),
        ),
        materials=_materials(
            spec,
            params,
            width * length,
            ("notion.crochet_hook", "notion.tapestry_needle", "notion.tape_measure"),
        ),
        warnings=tuple(warnings),
    )


def generate_crochet_flat_piece(spec: GarmentSpec, params: PatternParams) -> Pattern:
    width = params.dimensiones_cm.get("width", params.medidas_cm.get("width", 20.0))
    height = params.dimensiones_cm.get("length", params.medidas_cm.get("length", 20.0))
    return _flat_pattern(
        spec,
        params,
        family="crochet_flat_piece",
        title_key="title.flat_piece",
        section_id="flat_piece",
        section_key="section.flat_piece",
        width=width,
        length=height,
        warning=Warning("flat_piece", "warning.flat_piece"),
    )


def generate_crochet_bag(spec: GarmentSpec, params: PatternParams) -> Pattern:
    width = params.dimensiones_cm.get("width", params.medidas_cm.get("width", 30.0))
    height = params.dimensiones_cm.get("length", params.medidas_cm.get("length", 30.0))
    return _flat_pattern(
        spec,
        params,
        family="crochet_bag",
        title_key="title.bag",
        section_id="bag",
        section_key="section.bag",
        width=width,
        length=height,
        warning=Warning("bag_flat", "warning.bag_flat"),
    )


def generate_crochet_scarf(spec: GarmentSpec, params: PatternParams) -> Pattern:
    width = params.dimensiones_cm.get("width", params.medidas_cm.get("width", 25.0))
    length = params.dimensiones_cm.get("length", params.medidas_cm.get("length", 180.0))
    return _flat_pattern(
        spec,
        params,
        family="crochet_scarf",
        title_key="title.scarf",
        section_id="scarf",
        section_key="section.scarf",
        width=width,
        length=length,
    )


def granny_round_stitches(round_number: int) -> int:
    """Puntos (pa + cad) de la vuelta n de un granny clasico: 16n + 4."""
    return 16 * round_number + 4


def _granny_rounds(rounds: int) -> tuple[Step, ...]:
    steps: list[Step] = [
        build_step(1, 0, (Repeat(4, (Op(StitchKind.GRANNY_START),)),))
    ]
    for number in range(2, rounds + 1):
        sides = number - 2
        group: tuple[Op, ...] = (Op(StitchKind.GRANNY_CORNER),)
        if sides:
            group += (Op(StitchKind.GRANNY_SIDE, times=sides),)
        steps.append(
            build_step(number, granny_round_stitches(number - 1), (Repeat(4, group),))
        )
    return tuple(steps)


def generate_granny_square(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Granny square clasico en redondo: grupos de 3 pa, esquinas de 2 cad.

    Lado = 2 x vueltas x alto de una vuelta de pa (ASUNCION: el anillo central
    queda absorbido en la primera vuelta). Ver docs/fuentes.md.
    """
    if params.densidad is None:
        params = params.model_copy(
            update={"densidad": crochet_gauge(params.peso_hilo.value, "crochet_dc")}
        )
    gauge = resolve_gauge(params)
    size = params.dimensiones_cm.get("size", params.medidas_cm.get("size", 15.0))
    round_cm = 1.0 / gauge.rows_per_cm
    rounds = max(1, round_half_up(size / (2 * round_cm)))
    actual = 2 * rounds * round_cm
    steps = _granny_rounds(rounds)
    section = Section(
        id="granny_square",
        name_key="section.granny_square",
        mode="round",
        steps=steps,
        start_stitches=0,
        end_stitches=granny_round_stitches(rounds),
        target=SectionTarget(
            measurement_key="width",
            target_cm=size,
            tolerance_cm=round_cm,
            dimension="length",
        ),
        # Cada vuelta suma alto en los dos lados del cuadrado.
        meta={"row_count": 2 * rounds, "rounds": rounds},
        bind_off=True,
        note_keys=("pattern.granny_intro",),
    )
    warnings = _warnings(params)
    warnings.append(Warning("granny_classic", "warning.granny_classic"))
    colors = tuple(spec.colorwork.paleta) if spec.colorwork else ()
    if len(colors) > 1:
        letters = ", ".join(f"{chr(65 + i)} ({c})" for i, c in enumerate(colors))
        warnings.append(
            Warning(
                "granny_colors",
                "pattern.granny_colors",
                severity="info",
                params={"colors": letters},
            )
        )
    return Pattern(
        meta=_meta(spec, params, "granny_square", "title.granny_square"),
        spec=spec,
        params=params,
        sections=(section,),
        measurements=(
            # Tolerancia: media vuelta por lado es el error maximo de redondeo.
            Measurement(
                key="width", value_cm=actual, target_cm=size, tolerance_cm=round_cm, kind="width"
            ),
            Measurement(
                key="length", value_cm=actual, target_cm=size, tolerance_cm=round_cm, kind="length"
            ),
        ),
        materials=_materials(
            spec,
            params,
            actual * actual,
            ("notion.crochet_hook", "notion.tapestry_needle", "notion.tape_measure"),
        ),
        warnings=tuple(warnings),
    )
