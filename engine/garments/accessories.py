"""Accesorios y piezas del hogar: gorro, bufanda, cuello, mitones, medias,
chal y manta.

Las piezas planas se generan como rectangulos y las piezas tubulares en
redondo. Las simplificaciones (sin talon, mitones planos, chal rectangular)
se declaran en las advertencias.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from engine import ENGINE_VERSION
from engine.distribution import decrease_evenly
from engine.garments.acc_kit import nearest_multiple, repeat_tolerance
from engine.garments.base import ImpossibleProportionsError
from engine.gauge import Gauge
from engine.ir import (
    CountRef,
    JoinCheck,
    Materials,
    Measurement,
    Op,
    Pattern,
    PatternMeta,
    Section,
    SectionTarget,
    Step,
    Warning,
    build_step,
)
from engine.materials import default_needle_mm, estimate_yarn
from engine.rounding import round_half_up
from engine.spec import (
    GarmentSpec,
    PatternParams,
    StitchPatternName,
    resolve_gauge,
)
from engine.stitches.catalog import (
    adjust_stitches,
    catalog_id_for_name,
    expand_row,
    get_stitch,
    stitch_row_note,
)
from engine.stitches.kinds import StitchKind


def _dimension(params: PatternParams, key: str, default: float) -> float:
    if key in params.dimensiones_cm:
        return params.dimensiones_cm[key]
    if key in params.medidas_cm:
        return params.medidas_cm[key]
    return default


def _base_id(spec: GarmentSpec) -> str:
    pattern_id = catalog_id_for_name(
        spec.punto_base or StitchPatternName.STOCKINETTE
    )
    return "stockinette" if get_stitch(pattern_id).technique == "crochet" else pattern_id


def with_stitch_gauge(params: PatternParams, pattern_id: str) -> PatternParams:
    """Sin muestra medida: la densidad de referencia del hilo corregida por
    el punto (el punto lino o un elastico no miden lo mismo que el jersey).
    Los factores son ASUNCIONES documentadas en el catalogo."""
    sts, rows = get_stitch(pattern_id).gauge_factor
    if params.densidad is not None or (sts, rows) == (1.0, 1.0):
        return params
    base = resolve_gauge(params)
    gauge = Gauge(
        stitches_per_10cm=round(base.stitches_per_10cm * sts, 1),
        rows_per_10cm=round(base.rows_per_10cm * rows, 1),
    )
    return params.model_copy(update={"densidad": gauge})


def _meta(
    spec: GarmentSpec, params: PatternParams, family: str, title_key: str
) -> PatternMeta:
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
        needle_mm=params.aguja_mm or default_needle_mm(params.peso_hilo),
        hook_mm=None,
        meters=meters,
        grams=grams,
        notions=notions,
        colors=colors,
    )


def _common_warnings(params: PatternParams) -> list[Warning]:
    warnings = [
        Warning("gauge_sample", "warning.gauge_sample", severity="info"),
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", "warning.assumption", severity="info"),
    ]
    if params.medidas_cm:
        warnings.append(
            Warning("custom_measurements", "warning.custom_measurements", severity="info")
        )
    return warnings


def _flat_rect_section(
    section_id: str,
    name_key: str,
    stitches: int,
    rows: int,
    pattern_id: str,
    target_cm: float,
    *,
    note_key: str | None = None,
    note_keys: tuple[str, ...] = (),
) -> Section:
    pattern = get_stitch(pattern_id)
    steps: list[Step] = [
        build_step(
            1,
            0,
            (Op(StitchKind.CAST_ON, times=stitches),),
            note_key="pattern.note.cast_on_panel",
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
        note_keys=note_keys,
    )


def _round_tube_section(
    section_id: str,
    name_key: str,
    stitches: int,
    rows: int,
    pattern_id: str,
    target_cm: float,
    *,
    note_key: str | None = None,
    start_stitches: int | None = None,
    cast_on: bool = False,
    bind_off: bool = True,
) -> Section:
    pattern = get_stitch(pattern_id)
    steps: list[Step] = []
    if cast_on:
        steps.append(
            build_step(
                1,
                0,
                (Op(StitchKind.CAST_ON, times=stitches),),
                note_key="pattern.note.cast_on_join",
            )
        )
        first = 2
    else:
        first = 1
    for number in range(first, rows + first):
        steps.append(
            build_step(
                number,
                stitches,
                expand_row(pattern, stitches, number - first + 1, in_the_round=True),
                note_key=note_key if number == first else None,
            )
        )
    return Section(
        id=section_id,
        name_key=name_key,
        mode="round",
        steps=tuple(steps),
        start_stitches=0 if cast_on else (start_stitches or stitches),
        end_stitches=stitches,
        target=SectionTarget(
            measurement_key=f"{section_id}_length",
            target_cm=target_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": rows, "cast_on": stitches},
        bind_off=bind_off,
    )


def _rectangular(
    spec: GarmentSpec,
    params: PatternParams,
    *,
    family: str,
    title_key: str,
    section_id: str,
    section_key: str,
    default_width: float,
    default_length: float,
    warning: Warning | None = None,
) -> Pattern:
    width = _dimension(params, "width", default_width)
    length = _dimension(params, "length", default_length)
    pattern_id = _base_id(spec)
    if pattern_id == "other":
        pattern_id = "stockinette"
    params = with_stitch_gauge(params, pattern_id)
    gauge = resolve_gauge(params)
    multiple = get_stitch(pattern_id).multiple
    stitches = nearest_multiple(width * gauge.stitches_per_cm, multiple)
    rows = max(1, gauge.rows_for_cm(length))
    section = _flat_rect_section(
        section_id,
        section_key,
        stitches,
        rows,
        pattern_id,
        length,
        note_key=stitch_row_note(pattern_id, "pattern.note.flat_panel"),
    )
    warnings = _common_warnings(params)
    if warning is not None:
        warnings.append(warning)
    if pattern_id in {"stockinette", "reverse_stockinette"} and family in {"scarf", "shawl", "blanket"}:
        warnings.append(Warning("scarf_curl", "warning.scarf_curl"))
    from engine.garments.crochet import _repeat_warning, _width_tolerance

    width_tol = _width_tolerance(gauge, multiple, 1.5)
    warnings += _repeat_warning(gauge.cm_for_stitches(stitches), width, 1.5, params.idioma, pattern_id)
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
                tolerance_cm=width_tol,
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
            ("notion.tapestry_needle", "notion.tape_measure"),
        ),
        warnings=tuple(warnings),
    )


def generate_bag(spec: GarmentSpec, params: PatternParams) -> Pattern:
    return _rectangular(
        spec,
        params,
        family="bag",
        title_key="title.bag",
        section_id="bag",
        section_key="section.bag",
        default_width=30.0,
        default_length=30.0,
        warning=Warning("bag_flat", "warning.bag_flat"),
    )


def generate_flat_piece(spec: GarmentSpec, params: PatternParams) -> Pattern:
    return _rectangular(
        spec,
        params,
        family="flat_piece",
        title_key="title.flat_piece",
        section_id="flat_piece",
        section_key="section.flat_piece",
        default_width=20.0,
        default_length=20.0,
        warning=Warning("flat_piece", "warning.flat_piece"),
    )


def generate_scarf(spec: GarmentSpec, params: PatternParams) -> Pattern:
    return _rectangular(
        spec,
        params,
        family="scarf",
        title_key="title.scarf",
        section_id="scarf",
        section_key="section.scarf",
        default_width=25.0,
        default_length=180.0,
    )


def generate_shawl(spec: GarmentSpec, params: PatternParams) -> Pattern:
    return _rectangular(
        spec,
        params,
        family="shawl",
        title_key="title.shawl",
        section_id="shawl",
        section_key="section.shawl",
        default_width=60.0,
        default_length=180.0,
        warning=Warning("shawl_rectangular", "warning.shawl_rectangular"),
    )


def generate_blanket(spec: GarmentSpec, params: PatternParams) -> Pattern:
    return _rectangular(
        spec,
        params,
        family="blanket",
        title_key="title.blanket",
        section_id="blanket",
        section_key="section.blanket",
        default_width=100.0,
        default_length=120.0,
        warning=Warning("blanket_panel", "warning.blanket_panel"),
    )


def generate_cowl(spec: GarmentSpec, params: PatternParams) -> Pattern:
    gauge = resolve_gauge(params)
    circumference = _dimension(params, "circumference", 60.0)
    length = _dimension(params, "length", 30.0)
    stitches = adjust_stitches(
        max(4, round_half_up(circumference * gauge.stitches_per_cm)),
        4,
        mode="nearest",
    )
    rows = max(1, gauge.rows_for_cm(length))
    section = _round_tube_section(
        "cowl",
        "section.cowl",
        stitches,
        rows,
        "rib_2x2",
        length,
        note_key="pattern.note.cuff",
        cast_on=True,
    )
    return Pattern(
        meta=_meta(spec, params, "cowl", "title.cowl"),
        spec=spec,
        params=params,
        sections=(section,),
        measurements=(
            Measurement(
                key="circumference",
                value_cm=gauge.cm_for_stitches(stitches),
                target_cm=circumference,
                tolerance_cm=2.5,
                kind="circumference",
            ),
            Measurement(
                key="length",
                value_cm=gauge.cm_for_rows(rows),
                target_cm=length,
                tolerance_cm=1.0,
                kind="length",
            ),
        ),
        materials=_materials(
            spec,
            params,
            circumference * length,
            ("notion.stitch_markers", "notion.tape_measure"),
        ),
        warnings=tuple(_common_warnings(params)),
    )


def generate_hat(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Gorro de dos agujas: el calculo por estilo vive en engine/garments/hats.py."""
    from engine.garments.hats import generate_hat_style

    return generate_hat_style(spec, params)


def generate_mittens(spec: GarmentSpec, params: PatternParams) -> Pattern:
    pattern_id = _base_id(spec)
    if pattern_id == "other":
        pattern_id = "stockinette"
    params = with_stitch_gauge(params, pattern_id)
    gauge = resolve_gauge(params)
    multiple = get_stitch(pattern_id).multiple
    palm = _dimension(params, "palm", 20.0)
    hand_length = _dimension(params, "length", 18.0)
    thumb_length = _dimension(params, "thumb", 6.0)
    thumb_width = _dimension(params, "thumb_width", 6.0)
    pattern_id = _base_id(spec)
    if pattern_id == "other":
        pattern_id = "stockinette"
    # Los anchos respetan el multiplo del punto (antes: punto arroz con 13
    # pts fallaba al expandir la vuelta).
    multiple = get_stitch(pattern_id).multiple
    hand_sts = nearest_multiple((palm / 2.0) * gauge.stitches_per_cm, multiple, minimum=4)
    thumb_sts = nearest_multiple(thumb_width * gauge.stitches_per_cm, multiple, minimum=4)
    hand_rows = max(1, gauge.rows_for_cm(hand_length))
    thumb_rows = max(1, gauge.rows_for_cm(thumb_length))
    sections = (
        _flat_rect_section(
            "hand",
            "section.hand",
            hand_sts,
            hand_rows,
            pattern_id,
            hand_length,
            note_key="pattern.note.flat_panel",
            note_keys=("pattern.note.mittens_hand",),
        ),
        _flat_rect_section(
            "thumb",
            "section.thumb",
            thumb_sts,
            thumb_rows,
            pattern_id,
            thumb_length,
            note_key="pattern.note.flat_panel",
            note_keys=("pattern.note.mittens_thumb",),
        ),
    )
    warnings = _common_warnings(params)
    warnings.extend(
        [
            Warning("flat_panels", "warning.flat_panels"),
            Warning("mittens_flat", "warning.mittens_flat"),
        ]
    )
    return Pattern(
        meta=_meta(spec, params, "mittens", "title.mittens"),
        spec=spec,
        params=params,
        sections=sections,
        measurements=(
            Measurement(
                key="palm",
                value_cm=gauge.cm_for_stitches(2 * hand_sts),
                target_cm=palm,
                tolerance_cm=repeat_tolerance(gauge, 2 * multiple, 2.0),
                kind="circumference",
            ),
            Measurement(
                key="length",
                value_cm=gauge.cm_for_rows(hand_rows),
                target_cm=hand_length,
                tolerance_cm=1.0,
                kind="length",
            ),
            Measurement(
                key="thumb",
                value_cm=gauge.cm_for_rows(thumb_rows),
                target_cm=thumb_length,
                tolerance_cm=0.5,
                kind="length",
            ),
        ),
        materials=_materials(
            spec,
            params,
            2 * (palm / 2.0) * hand_length + 2 * thumb_width * thumb_length,
            ("notion.tapestry_needle", "notion.tape_measure"),
        ),
        warnings=tuple(warnings),
    )


def generate_socks(spec: GarmentSpec, params: PatternParams) -> Pattern:
    gauge = resolve_gauge(params)
    circumference = _dimension(params, "circumference", 22.0)
    foot_length = _dimension(params, "foot_length", 24.0)
    cuff_cm = 4.0
    leg_cm = _dimension(params, "leg", 10.0)
    stitches = adjust_stitches(
        max(8, round_half_up(circumference * gauge.stitches_per_cm)),
        4,
        mode="nearest",
    )
    cuff_rows = max(1, gauge.rows_for_cm(cuff_cm))
    leg_rows = max(1, gauge.rows_for_cm(leg_cm))
    toe_rows = max(1, (stitches - 8) // 4)
    toe_cm = gauge.cm_for_rows(toe_rows)
    foot_rows = max(1, gauge.rows_for_cm(foot_length - toe_cm))
    if foot_length <= toe_cm + 1:
        raise ImpossibleProportionsError(
            "error.impossible_proportions", yoke=0, body=foot_length, sleeve=0
        )
    cuff = _round_tube_section(
        "cuff",
        "section.cuff",
        stitches,
        cuff_rows,
        "rib_2x2",
        cuff_cm,
        note_key="pattern.note.cuff",
        cast_on=True,
    )
    leg = _round_tube_section(
        "leg",
        "section.leg",
        stitches,
        leg_rows,
        "stockinette",
        leg_cm,
        note_key="pattern.note.flat_panel",
        start_stitches=stitches,
    )
    foot = _round_tube_section(
        "foot",
        "section.foot",
        stitches,
        foot_rows,
        "stockinette",
        gauge.cm_for_rows(foot_rows),
        note_key="pattern.note.flat_panel",
        start_stitches=stitches,
    )
    steps: list[Step] = []
    current = stitches
    for number in range(1, toe_rows + 1):
        items, current = decrease_evenly(current, 4, StitchKind.K2TOG)
        steps.append(
            build_step(
                number,
                current + 4,
                items,
                note_key="pattern.note.toe",
            )
        )
    toe = Section(
        id="toe",
        name_key="section.toe",
        mode="round",
        steps=tuple(steps),
        start_stitches=stitches,
        end_stitches=current,
        target=SectionTarget(
            measurement_key="toe_length",
            target_cm=toe_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": toe_rows},
        bind_off=True,
    )
    warnings = _common_warnings(params)
    warnings.append(Warning("sock_tube", "warning.sock_tube"))
    return Pattern(
        meta=_meta(spec, params, "socks", "title.socks"),
        spec=spec,
        params=params,
        sections=(cuff, leg, foot, toe),
        measurements=(
            Measurement(
                key="circumference",
                value_cm=gauge.cm_for_stitches(stitches),
                target_cm=circumference,
                tolerance_cm=2.5,
                kind="circumference",
            ),
            Measurement(
                key="foot_length",
                value_cm=gauge.cm_for_rows(foot_rows + toe_rows),
                target_cm=foot_length,
                tolerance_cm=1.5,
                kind="length",
            ),
        ),
        materials=_materials(
            spec,
            params,
            circumference * (cuff_cm + leg_cm + foot_length),
            ("notion.stitch_markers", "notion.tape_measure"),
        ),
        warnings=tuple(warnings),
        joins=(
            JoinCheck(
                label_key="join.cuff",
                left=(CountRef("cuff", "end"),),
                right=(CountRef("leg", "start"),),
            ),
            JoinCheck(
                label_key="join.foot",
                left=(CountRef("leg", "end"),),
                right=(CountRef("foot", "start"),),
            ),
            JoinCheck(
                label_key="join.toe",
                left=(CountRef("foot", "end"),),
                right=(CountRef("toe", "start"),),
            ),
        ),
    )
