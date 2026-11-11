"""Pullover con canesu circular (yoke) top-down.

El canesu es una pieza circular que crece desde el cuello hasta la separation
de cuerpo y mangas. Los aumentos se reparten de forma uniforme; no hay lineas
de raglan. La version actual no genera el grafico de jacquard: si la foto
muestra colorwork, se conserva la paleta y se advierte que el motivo debe
disenarse aparte.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from engine import ENGINE_VERSION
from engine.distribution import (
    decrease_evenly,
    even_positions,
    increase_evenly,
    regular_rows,
    split_even,
)
from engine.garments.base import ImpossibleProportionsError
from engine.garments.panels import body_round_with_panels, compensation, panel_for, texture_motif
from engine.gauge import Gauge
from engine.i18n import t
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
    division_ops,
)
from engine.materials import default_needle_mm, estimate_yarn
from engine.rounding import round_half_up
from engine.sizes import BodySize, ease_for_fit, resolve_body_size
from engine.spec import (
    BodyLength,
    ColorworkType,
    GarmentSpec,
    Neckline,
    PatternParams,
    SleeveLength,
    StitchPatternName,
    resolve_gauge,
)
from engine.stitches.catalog import (
    adjust_stitches,
    catalog_id_for_name,
    expand_row,
    get_stitch,
)
from engine.stitches.kinds import StitchKind

HEM_CM = 4.0
CUFF_CM = 4.0
NECKBAND_CM = 3.0
UNDERARM_CM = 4.0
SLEEVE_EASE_CM = 4.0
CUFF_EASE_CM = 2.0
YOKE_EASE_CM = 4.0
MEASUREMENT_TOLERANCE_CM = 2.5


@dataclass(frozen=True)
class YokePlan:
    neck_sts: int
    yoke_sts: int
    yoke_rows: int
    yoke_depth_cm: float
    total_increases: int
    increase_rounds: int
    body_sts: int
    body_before: int
    body_rows: int
    body_underarm_cm: float
    hem_rows: int
    sleeve_sts: int
    sleeve_before: int
    sleeve_rows: int
    sleeve_underarm_cm: float
    cuff_sts: int
    cuff_rows: int
    sleeve_decreases: int
    underarm_sts: int
    neckband_cm: float
    body_length_cm: float
    sleeve_length_cm: float
    bust_target_cm: float
    neck_target_cm: float


def _body_length_cm(spec: GarmentSpec, size: BodySize) -> float:
    length = spec.largo_cuerpo or BodyLength.HIP
    if length is BodyLength.CROPPED:
        return max(20.0, size.body_length_cm - 15.0)
    if length is BodyLength.TUNIC:
        return size.body_length_cm + 8.0
    if length is BodyLength.LONG:
        return size.body_length_cm + 15.0
    return size.body_length_cm


def _sleeve_length_cm(spec: GarmentSpec, size: BodySize) -> float:
    length = spec.largo_manga or SleeveLength.LONG
    if length is SleeveLength.LONG:
        return size.sleeve_length_cm
    if length is SleeveLength.THREE_QUARTER:
        return size.sleeve_length_cm * 0.75
    if length is SleeveLength.SHORT:
        return size.sleeve_length_cm * 0.45
    raise ImpossibleProportionsError(
        "error.unsupported_sleeve", length=length.value
    )


def _neck_cm(spec: GarmentSpec, size: BodySize) -> float:
    neckline = spec.escote
    if neckline is Neckline.BOAT:
        return size.neck_cm + 6.0
    if neckline in {Neckline.V_NECK, Neckline.SQUARE}:
        return size.neck_cm + 2.0
    if neckline in {Neckline.TURTLENECK, Neckline.FUNNEL}:
        return size.neck_cm - 1.0
    if neckline is Neckline.HOOD:
        return size.neck_cm + 4.0
    return size.neck_cm


def _neckband_cm(spec: GarmentSpec) -> float:
    if spec.escote in {Neckline.TURTLENECK, Neckline.FUNNEL}:
        return 8.0
    return NECKBAND_CM


def plan_yoke(
    spec: GarmentSpec, params: PatternParams
) -> tuple[YokePlan, Gauge, BodySize]:
    size = resolve_body_size(params.talla, params.medidas_cm)
    gauge = resolve_gauge(params)
    ease = params.ease_cm if params.ease_cm is not None else ease_for_fit(spec.ajuste)
    body_length_cm = _body_length_cm(spec, size)
    sleeve_length_cm = _sleeve_length_cm(spec, size)
    neck_cm = _neck_cm(spec, size)
    neckband_cm = _neckband_cm(spec)

    underarm_sts = adjust_stitches(
        max(2, gauge.stitches_for_cm(UNDERARM_CM)), 2, mode="nearest"
    )
    body_target = max(
        8,
        round_half_up((size.bust_cm + ease) * gauge.stitches_per_cm / 4.0) * 4,
    )
    sleeve_target = max(
        4,
        round_half_up((size.upper_arm_cm + SLEEVE_EASE_CM) * gauge.stitches_per_cm / 2.0)
        * 2,
    )
    body_before = body_target - 2 * underarm_sts
    sleeve_before = sleeve_target - underarm_sts
    if body_before <= 0 or sleeve_before <= 0:
        raise ImpossibleProportionsError(
            "error.impossible_proportions", yoke=0, body=body_target, sleeve=sleeve_target
        )
    yoke_sts = body_before + 2 * sleeve_before
    neck_sts = max(
        16, round_half_up(neck_cm * gauge.stitches_per_cm / 4.0) * 4
    )
    total_increases = yoke_sts - neck_sts
    if total_increases <= 0:
        raise ImpossibleProportionsError(
            "error.impossible_proportions", yoke=0, body=body_target, sleeve=sleeve_target
        )
    yoke_depth_cm = size.armhole_cm + YOKE_EASE_CM
    if (spec.largo_manga or SleeveLength.LONG) is SleeveLength.SHORT:
        yoke_depth_cm = max(16.0, sleeve_length_cm - CUFF_CM - 4.0)
    yoke_rows = max(1, gauge.rows_for_cm(yoke_depth_cm))
    if body_length_cm <= yoke_depth_cm + HEM_CM + 2:
        raise ImpossibleProportionsError(
            "error.impossible_proportions",
            yoke=round(yoke_depth_cm, 1),
            body=body_length_cm,
            sleeve=sleeve_length_cm,
        )
    if sleeve_length_cm <= yoke_depth_cm + CUFF_CM + 2:
        raise ImpossibleProportionsError(
            "error.impossible_proportions",
            yoke=round(yoke_depth_cm, 1),
            body=body_length_cm,
            sleeve=sleeve_length_cm,
        )

    body_underarm_cm = body_length_cm - yoke_depth_cm - HEM_CM
    body_rows = max(1, gauge.rows_for_cm(body_underarm_cm))
    hem_rows = max(1, gauge.rows_for_cm(HEM_CM))
    sleeve_underarm_cm = sleeve_length_cm - yoke_depth_cm - CUFF_CM
    sleeve_rows = max(1, gauge.rows_for_cm(sleeve_underarm_cm))
    cuff_rows = max(1, gauge.rows_for_cm(CUFF_CM))

    sleeve_kind = spec.largo_manga or SleeveLength.LONG
    cuff_target_cm = size.wrist_cm + CUFF_EASE_CM
    if sleeve_kind is SleeveLength.THREE_QUARTER:
        cuff_target_cm += 2.0
    cuff_sts = max(
        4, round_half_up(cuff_target_cm * gauge.stitches_per_cm / 4.0) * 4
    )
    if cuff_sts >= sleeve_target:
        cuff_sts = max(4, sleeve_target - (sleeve_target % 4))
    sleeve_decreases = sleeve_target - cuff_sts

    increase_rounds = min(yoke_rows, total_increases)
    plan = YokePlan(
        neck_sts=neck_sts,
        yoke_sts=yoke_sts,
        yoke_rows=yoke_rows,
        yoke_depth_cm=yoke_depth_cm,
        total_increases=total_increases,
        increase_rounds=increase_rounds,
        body_sts=body_target,
        body_before=body_before,
        body_rows=body_rows,
        body_underarm_cm=body_underarm_cm,
        hem_rows=hem_rows,
        sleeve_sts=sleeve_target,
        sleeve_before=sleeve_before,
        sleeve_rows=sleeve_rows,
        sleeve_underarm_cm=sleeve_underarm_cm,
        cuff_sts=cuff_sts,
        cuff_rows=cuff_rows,
        sleeve_decreases=sleeve_decreases,
        underarm_sts=underarm_sts,
        neckband_cm=neckband_cm,
        body_length_cm=body_length_cm,
        sleeve_length_cm=sleeve_length_cm,
        bust_target_cm=size.bust_cm + ease,
        neck_target_cm=neck_cm,
    )
    return plan, gauge, size


def _neckband_section(plan: YokePlan, gauge: Gauge) -> Section:
    rib = get_stitch("rib_1x1")
    steps = tuple(
        build_step(
            number,
            plan.neck_sts,
            expand_row(rib, plan.neck_sts, number, in_the_round=True),
            note_key="pattern.note.neckband" if number == 1 else None,
        )
        for number in range(1, max(1, gauge.rows_for_cm(plan.neckband_cm)) + 1)
    )
    return Section(
        id="neckband",
        name_key="section.neckband",
        mode="round",
        steps=steps,
        start_stitches=plan.neck_sts,
        end_stitches=plan.neck_sts,
        target=SectionTarget(
            measurement_key="neckband_length",
            target_cm=plan.neckband_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": max(1, gauge.rows_for_cm(plan.neckband_cm))},
    )


def _yoke_section(plan: YokePlan) -> Section:
    steps: list[Step] = [
        build_step(
            1,
            plan.neck_sts,
            (Op(StitchKind.KNIT, times=plan.neck_sts),),
            note_key="pattern.note.yoke_circular_setup",
        )
    ]
    increase_counts = split_even(plan.total_increases, plan.increase_rounds)
    increase_positions = set(even_positions(plan.yoke_rows, plan.increase_rounds))
    current = plan.neck_sts
    next_count = 0
    for row in range(1, plan.yoke_rows + 1):
        number = row + 1
        if row in increase_positions:
            count = increase_counts[next_count]
            next_count += 1
            items, current = increase_evenly(current, count)
            steps.append(
                build_step(
                    number,
                    current - count,
                    items,
                    note_key="pattern.note.increase_yoke",
                )
            )
        else:
            steps.append(
                build_step(
                    number,
                    current,
                    (Op(StitchKind.KNIT, times=current),),
                    note_key="pattern.note.plain",
                )
            )
    if current != plan.yoke_sts:
        raise RuntimeError(
            f"canesu: termina con {current} puntos, se esperaban {plan.yoke_sts}"
        )
    return Section(
        id="yoke",
        name_key="section.yoke",
        mode="round",
        steps=tuple(steps),
        start_stitches=plan.neck_sts,
        end_stitches=plan.yoke_sts,
        target=SectionTarget(
            measurement_key="yoke_depth",
            target_cm=plan.yoke_depth_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={
            "row_count": plan.yoke_rows,
            "expected_increases": plan.total_increases,
            "expected_decreases": 0,
            "body_before": plan.body_before,
            "sleeve_before": plan.sleeve_before,
            "body": plan.body_sts,
            "sleeve": plan.sleeve_sts,
            "underarm": plan.underarm_sts,
        },
    )


def _body_section(plan: YokePlan, spec: GarmentSpec, params: PatternParams) -> Section:
    # Orden fisico: espalda, manga, delantero, manga.
    half = plan.body_before // 2
    division = (
        ("knit", half),
        ("hold", plan.sleeve_before),
        ("cast_on", plan.underarm_sts),
        ("knit", plan.body_before - half),
        ("hold", plan.sleeve_before),
        ("cast_on", plan.underarm_sts),
    )
    first = build_step(
        1, plan.body_before, division_ops(division), note_key="pattern.note.separation"
    )
    panel = panel_for(spec, division)
    extra = 0
    if panel is not None:
        extra = compensation(panel, resolve_gauge(params).stitches_per_cm, params.panel_motivo_cm)
        if plan.body_rows < 4:
            extra = 0
    last_round = plan.body_rows
    steps: list[Step] = [first]
    for number in range(2, plan.body_rows + 1):
        steps.append(
            build_step(
                number,
                plan.body_sts + (2 * extra if number > 2 else 0),
                body_round_with_panels(
                    division,
                    panel,
                    number - 1,
                    extra=extra,
                    stage=(
                        "increase" if number == 2 else "decrease" if number == last_round else "compensated"
                    ),
                )
                if panel is not None
                else (Op(StitchKind.KNIT, times=plan.body_sts),),
                note_key=(
                    "pattern.note.panel_compensation_inc"
                    if extra and number == 2
                    else "pattern.note.panel_compensation_dec"
                    if extra and number == last_round
                    else None
                ),
            )
        )
    return Section(
        division=division,
        id="body",
        name_key="section.body",
        mode="round",
        steps=tuple(steps),
        start_stitches=plan.body_before,
        end_stitches=plan.body_sts,
        target=SectionTarget(
            measurement_key="body_underarm_length",
            target_cm=plan.body_underarm_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={
            **(
                {"panel_rows": panel.rows, "panel_repeats": panel.repeats, "panel_width": panel.width}
                if panel is not None
                else {}
            ),
            "row_count": plan.body_rows,
            "underarm_cast_on": 2 * plan.underarm_sts,
            "underarm": plan.underarm_sts,
            "body_before": plan.body_before,
            "body": plan.body_sts,
            "sleeve_final": plan.sleeve_sts,
        },
    )


def _hem_section(plan: YokePlan) -> Section:
    rib = get_stitch("rib_2x2")
    steps = tuple(
        build_step(
            number,
            plan.body_sts,
            expand_row(rib, plan.body_sts, number, in_the_round=True),
            note_key="pattern.note.hem" if number == 1 else None,
        )
        for number in range(1, plan.hem_rows + 1)
    )
    return Section(
        id="hem",
        name_key="section.hem",
        mode="round",
        steps=steps,
        start_stitches=plan.body_sts,
        end_stitches=plan.body_sts,
        target=SectionTarget(
            measurement_key="hem_length",
            target_cm=HEM_CM,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": plan.hem_rows},
        bind_off=True,
    )


def _sleeve_section(side: str, plan: YokePlan) -> Section:
    decrease_rounds = min(plan.sleeve_rows, plan.sleeve_decreases)
    counts = (
        split_even(plan.sleeve_decreases, decrease_rounds)
        if decrease_rounds
        else []
    )
    positions = (
        set(regular_rows(plan.sleeve_rows, decrease_rounds))
        if decrease_rounds
        else set()
    )
    steps: list[Step] = []
    current = plan.sleeve_sts
    next_count = 0
    for number in range(1, plan.sleeve_rows + 1):
        if number in positions:
            count = counts[next_count]
            next_count += 1
            items, new_count = decrease_evenly(current, count)
            steps.append(
                build_step(
                    number,
                    current,
                    items,
                    note_key="pattern.note.decrease_sleeve",
                )
            )
            current = new_count
        else:
            steps.append(
                build_step(
                    number,
                    current,
                    (Op(StitchKind.KNIT, times=current),),
                    note_key="pattern.note.sleeve_pickup" if number == 1 else None,
                )
            )
    if current != plan.cuff_sts:
        raise RuntimeError(
            f"manga {side}: termina con {current} puntos, se esperaban {plan.cuff_sts}"
        )
    return Section(
        id=f"sleeve_{side}",
        name_key=f"section.sleeve_{side}",
        mode="round",
        steps=tuple(steps),
        start_stitches=plan.sleeve_sts,
        end_stitches=plan.cuff_sts,
        target=SectionTarget(
            measurement_key="sleeve_underarm_length",
            target_cm=plan.sleeve_underarm_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={
            "row_count": plan.sleeve_rows,
            "picked_up": plan.underarm_sts,
            "decreases": plan.sleeve_decreases,
        },
    )


def _cuff_section(side: str, plan: YokePlan) -> Section:
    rib = get_stitch("rib_2x2")
    steps = tuple(
        build_step(
            number,
            plan.cuff_sts,
            expand_row(rib, plan.cuff_sts, number, in_the_round=True),
            note_key="pattern.note.cuff" if number == 1 else None,
        )
        for number in range(1, plan.cuff_rows + 1)
    )
    return Section(
        id=f"cuff_{side}",
        name_key="section.cuff",
        mode="round",
        steps=steps,
        start_stitches=plan.cuff_sts,
        end_stitches=plan.cuff_sts,
        target=SectionTarget(
            measurement_key="cuff_length",
            target_cm=CUFF_CM,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": plan.cuff_rows},
        bind_off=True,
    )


def _warnings(
    spec: GarmentSpec,
    params: PatternParams,
    base_id: str,
) -> tuple[Warning, ...]:
    warnings: list[Warning] = [
        Warning("gauge_sample", "warning.gauge_sample", severity="info"),
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", "warning.assumption", severity="info"),
        Warning("no_short_rows", "warning.no_short_rows"),
    ]
    if spec.colorwork and spec.colorwork.tipo is not ColorworkType.NONE:
        warnings.append(
            Warning("colorwork_not_charted", "warning.colorwork_not_charted")
        )
    if params.medidas_cm:
        warnings.append(
            Warning("custom_measurements", "warning.custom_measurements", severity="info")
        )
    motif = texture_motif(spec)
    if motif is not None:
        warnings.append(
            Warning(
                "texture_panel",
                "warning.texture_panel_compensated" if params.panel_motivo_cm else "warning.texture_panel",
                params={
                    "stitch": t(get_stitch(motif).name_key, params.idioma),
                    "cm": f"{params.panel_motivo_cm or 0:g}",
                },
            )
        )
    elif base_id != "stockinette":
        stitch_name = t(get_stitch(base_id).name_key, params.idioma)
        warnings.append(
            Warning(
                "stitch_fallback",
                "warning.stitch_fallback",
                params={"stitch": stitch_name},
            )
        )
    return tuple(warnings)


def _measurements(
    plan: YokePlan, gauge: Gauge, size: BodySize
) -> tuple[Measurement, ...]:
    return (
        Measurement(
            key="bust",
            value_cm=gauge.cm_for_stitches(plan.body_sts),
            target_cm=plan.bust_target_cm,
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="circumference",
        ),
        Measurement(
            key="body_length",
            value_cm=gauge.cm_for_rows(plan.yoke_rows + plan.body_rows + plan.hem_rows),
            target_cm=plan.body_length_cm,
            tolerance_cm=1.0,
            kind="length",
        ),
        Measurement(
            key="sleeve_length",
            value_cm=gauge.cm_for_rows(plan.yoke_rows + plan.sleeve_rows + plan.cuff_rows),
            target_cm=plan.sleeve_length_cm,
            tolerance_cm=1.0,
            kind="length",
        ),
        Measurement(
            key="upper_arm",
            value_cm=gauge.cm_for_stitches(plan.sleeve_sts),
            target_cm=size.upper_arm_cm + SLEEVE_EASE_CM,
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="circumference",
        ),
        Measurement(
            key="neck",
            value_cm=gauge.cm_for_stitches(plan.neck_sts),
            target_cm=plan.neck_target_cm,
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="circumference",
        ),
        Measurement(
            key="yoke_depth",
            value_cm=gauge.cm_for_rows(plan.yoke_rows),
            target_cm=plan.yoke_depth_cm,
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="length",
        ),
    )


def generate_yoke(spec: GarmentSpec, params: PatternParams) -> Pattern:
    plan, gauge, size = plan_yoke(spec, params)
    base_id = catalog_id_for_name(spec.punto_base or StitchPatternName.STOCKINETTE)
    if base_id == "other":
        base_id = "stockinette"
    sections = (
        _neckband_section(plan, gauge),
        _yoke_section(plan),
        _body_section(plan, spec, params),
        _hem_section(plan),
        _sleeve_section("left", plan),
        _cuff_section("left", plan),
        _sleeve_section("right", plan),
        _cuff_section("right", plan),
    )
    body_area = (
        gauge.cm_for_stitches(plan.body_sts)
        * gauge.cm_for_rows(plan.body_rows + plan.yoke_rows)
    )
    sleeve_area = (
        2
        * gauge.cm_for_stitches(plan.sleeve_sts)
        * gauge.cm_for_rows(plan.sleeve_rows + plan.cuff_rows)
    )
    band_area = gauge.cm_for_stitches(plan.neck_sts) * plan.neckband_cm
    meters, grams = estimate_yarn(body_area + sleeve_area + band_area, params.peso_hilo)
    notions = (
        "notion.stitch_markers",
        "notion.tapestry_needle",
        "notion.row_counter",
        "notion.tape_measure",
    )
    colors = tuple(spec.colorwork.paleta) if spec.colorwork else ()
    digest = hashlib.sha256(
        (spec.model_dump_json() + params.model_dump_json()).encode("utf-8")
    ).hexdigest()[:12]
    meta = PatternMeta(
        id=digest,
        family="yoke",
        title_key="title.pullover_yoke",
        size=size.key,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        engine_version=ENGINE_VERSION,
    )
    materials = Materials(
        yarn_weight=params.peso_hilo,
        needle_mm=params.aguja_mm or default_needle_mm(params.peso_hilo),
        hook_mm=None,
        meters=meters,
        grams=grams,
        notions=notions,
        colors=colors,
    )
    joins = (
        JoinCheck(
            label_key="join.neck",
            left=(CountRef("neckband", "end"),),
            right=(CountRef("yoke", "start"),),
        ),
        JoinCheck(
            label_key="join.underarm",
            left=(CountRef("body", "meta:underarm_cast_on"),),
            right=(
                CountRef("sleeve_left", "meta:picked_up"),
                CountRef("sleeve_right", "meta:picked_up"),
            ),
        ),
        JoinCheck(
            label_key="join.hem",
            left=(CountRef("body", "end"),),
            right=(CountRef("hem", "start"),),
        ),
        JoinCheck(
            label_key="join.cuff_left",
            left=(CountRef("sleeve_left", "end"),),
            right=(CountRef("cuff_left", "start"),),
        ),
        JoinCheck(
            label_key="join.cuff_right",
            left=(CountRef("sleeve_right", "end"),),
            right=(CountRef("cuff_right", "start"),),
        ),
    )
    return Pattern(
        meta=meta,
        spec=spec,
        params=params,
        sections=sections,
        measurements=_measurements(plan, gauge, size),
        materials=materials,
        warnings=_warnings(spec, params, base_id),
        joins=joins,
    )
