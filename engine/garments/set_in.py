"""Pullover con manga encajada, tejido en piezas planas.

La version actual simplifica la sisa y la copa de manga con disminuciones
parejas en los bordes. Las piezas se cosen; no se modela el escote con
hileras cortas ni una curva completa de copa. Las limitaciones se declaran en
las advertencias.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from engine import ENGINE_VERSION
from engine.distribution import (
    increase_evenly,
    paired_decreases,
    regular_rows,
    split_even,
)
from engine.garments.base import ImpossibleProportionsError
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
)
from engine.materials import default_needle_mm, estimate_yarn
from engine.rounding import round_half_up
from engine.sizes import BodySize, ease_for_fit, resolve_body_size
from engine.spec import (
    BodyLength,
    GarmentSpec,
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

CUFF_CM = 4.0
NECKBAND_CM = 3.0
SLEEVE_EASE_CM = 4.0
CUFF_EASE_CM = 2.0
MEASUREMENT_TOLERANCE_CM = 2.5


@dataclass(frozen=True)
class SetInPlan:
    body_sts: int
    shoulder_sts: int
    body_rows: int
    body_plain_rows: int
    armhole_dec_rows: int
    armhole_cm: float
    cuff_sts: int
    cuff_rows: int
    sleeve_upper_sts: int
    sleeve_body_rows: int
    sleeve_cap_rows: int
    sleeve_cap_top: int
    neck_sts: int
    neckband_rows: int
    body_length_cm: float
    sleeve_length_cm: float
    ease: float


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


def plan_set_in(
    spec: GarmentSpec, params: PatternParams
) -> tuple[SetInPlan, Gauge, BodySize]:
    size = resolve_body_size(params.talla, params.medidas_cm)
    gauge = resolve_gauge(params)
    ease = params.ease_cm if params.ease_cm is not None else ease_for_fit(spec.ajuste)
    body_length_cm = _body_length_cm(spec, size)
    sleeve_length_cm = _sleeve_length_cm(spec, size)
    panel_exact = (size.bust_cm + ease) * gauge.stitches_per_cm / 2.0
    body_sts = max(4, round_half_up(panel_exact / 2.0) * 2)
    body_rows = max(3, gauge.rows_for_cm(body_length_cm))
    armhole_cm = size.armhole_cm
    armhole_rows = max(2, gauge.rows_for_cm(armhole_cm))
    dec_rows = max(1, armhole_rows // 2)
    dec_rows = min(dec_rows, max(1, (body_sts - 4) // 2))
    dec_rows = min(dec_rows, max(1, (body_rows - 2) // 2))
    body_plain_rows = max(1, body_rows - 2 * dec_rows - 1)
    shoulder_sts = body_sts - 2 * dec_rows
    if shoulder_sts <= 0:
        raise ImpossibleProportionsError(
            "error.impossible_proportions", yoke=0, body=body_length_cm, sleeve=sleeve_length_cm
        )

    cuff_sts = max(
        4,
        round_half_up((size.wrist_cm + CUFF_EASE_CM) * gauge.stitches_per_cm / 4.0)
        * 4,
    )
    sleeve_exact = (size.upper_arm_cm + SLEEVE_EASE_CM) * gauge.stitches_per_cm
    sleeve_upper_sts = max(4, round_half_up(sleeve_exact / 2.0) * 2)
    if sleeve_upper_sts <= cuff_sts:
        raise ImpossibleProportionsError(
            "error.impossible_proportions", yoke=0, body=body_length_cm, sleeve=sleeve_length_cm
        )
    dec_rows = min(dec_rows, max(1, (sleeve_upper_sts - 2) // 2))
    shoulder_sts = body_sts - 2 * dec_rows
    body_plain_rows = max(1, body_rows - 2 * dec_rows - 1)
    cap_top = sleeve_upper_sts - 2 * dec_rows
    if cap_top <= 0 or shoulder_sts <= 0:
        raise ImpossibleProportionsError(
            "error.impossible_proportions", yoke=0, body=body_length_cm, sleeve=sleeve_length_cm
        )

    cuff_rows = max(1, gauge.rows_for_cm(CUFF_CM))
    sleeve_body_cm = sleeve_length_cm - CUFF_CM - armhole_cm
    if sleeve_body_cm <= 0:
        raise ImpossibleProportionsError(
            "error.impossible_proportions",
            yoke=round(armhole_cm, 1),
            body=body_length_cm,
            sleeve=sleeve_length_cm,
        )
    sleeve_body_rows = max(1, gauge.rows_for_cm(sleeve_body_cm))
    sleeve_cap_rows = 2 * dec_rows
    neck_sts = adjust_stitches(
        max(4, round_half_up(size.neck_cm * gauge.stitches_per_cm / 2.0) * 2),
        2,
        mode="nearest",
    )
    neckband_rows = max(1, gauge.rows_for_cm(NECKBAND_CM))
    plan = SetInPlan(
        body_sts=body_sts,
        shoulder_sts=shoulder_sts,
        body_rows=body_rows,
        body_plain_rows=body_plain_rows,
        armhole_dec_rows=dec_rows,
        armhole_cm=armhole_cm,
        cuff_sts=cuff_sts,
        cuff_rows=cuff_rows,
        sleeve_upper_sts=sleeve_upper_sts,
        sleeve_body_rows=sleeve_body_rows,
        sleeve_cap_rows=sleeve_cap_rows,
        sleeve_cap_top=cap_top,
        neck_sts=neck_sts,
        neckband_rows=neckband_rows,
        body_length_cm=body_length_cm,
        sleeve_length_cm=sleeve_length_cm,
        ease=ease,
    )
    return plan, gauge, size


def _body_panel(section_id: str, name_key: str, plan: SetInPlan) -> Section:
    steps: list[Step] = [
        build_step(
            1,
            0,
            (Op(StitchKind.CAST_ON, times=plan.body_sts),),
            note_key="pattern.note.cast_on_panel",
        )
    ]
    number = 2
    current = plan.body_sts
    for _ in range(plan.body_plain_rows):
        steps.append(
            build_step(
                number,
                current,
                (Op(StitchKind.KNIT, times=current),),
                note_key="pattern.note.flat_panel" if number == 2 else None,
            )
        )
        number += 1
    for _ in range(plan.armhole_dec_rows):
        ops, new_count = paired_decreases(current, 1, 1)
        steps.append(
            build_step(
                number,
                current,
                ops,
                note_key="pattern.note.armhole_shaping",
            )
        )
        current = new_count
        number += 1
        steps.append(
            build_step(
                number,
                current,
                (Op(StitchKind.KNIT, times=current),),
            )
        )
        number += 1
    if current != plan.shoulder_sts:
        raise RuntimeError(
            f"{section_id}: termina con {current}, se esperaban {plan.shoulder_sts}"
        )
    return Section(
        id=section_id,
        name_key=name_key,
        mode="flat",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=current,
        target=SectionTarget(
            measurement_key=f"{section_id}_length",
            target_cm=plan.body_length_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={
            "row_count": plan.body_rows,
            "cast_on": plan.body_sts,
            "armhole_decreases": 2 * plan.armhole_dec_rows,
            "shoulder": plan.shoulder_sts,
        },
        bind_off=True,
    )


def _cuff(side: str, plan: SetInPlan) -> Section:
    rib = get_stitch("rib_2x2")
    steps: list[Step] = [
        build_step(
            1,
            0,
            (Op(StitchKind.CAST_ON, times=plan.cuff_sts),),
            note_key="pattern.note.cast_on_panel",
        )
    ]
    for number in range(2, plan.cuff_rows + 2):
        steps.append(
            build_step(
                number,
                plan.cuff_sts,
                expand_row(rib, plan.cuff_sts, number - 1),
                note_key="pattern.note.cuff" if number == 2 else None,
            )
        )
    return Section(
        id=f"cuff_{side}",
        name_key="section.cuff",
        mode="flat",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=plan.cuff_sts,
        target=SectionTarget(
            measurement_key=f"cuff_{side}_length",
            target_cm=CUFF_CM,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": plan.cuff_rows, "cast_on": plan.cuff_sts},
        bind_off=True,
    )


def _sleeve(side: str, plan: SetInPlan) -> Section:
    increases = plan.sleeve_upper_sts - plan.cuff_sts
    increase_rounds = min(plan.sleeve_body_rows, increases)
    counts = (
        split_even(increases, increase_rounds) if increase_rounds else []
    )
    positions = (
        set(regular_rows(plan.sleeve_body_rows, increase_rounds))
        if increase_rounds
        else set()
    )
    steps: list[Step] = []
    current = plan.cuff_sts
    next_count = 0
    for number in range(1, plan.sleeve_body_rows + 1):
        if number in positions:
            count = counts[next_count]
            next_count += 1
            items, current = increase_evenly(current, count)
            steps.append(
                build_step(
                    number,
                    current - count,
                    items,
                    note_key="pattern.note.flat_panel" if number == 1 else None,
                )
            )
        else:
            steps.append(
                build_step(
                    number,
                    current,
                    (Op(StitchKind.KNIT, times=current),),
                    note_key="pattern.note.flat_panel" if number == 1 else None,
                )
            )
    if current != plan.sleeve_upper_sts:
        raise RuntimeError(
            f"manga {side}: termina el cuerpo con {current}, se esperaban "
            f"{plan.sleeve_upper_sts}"
        )
    number = plan.sleeve_body_rows + 1
    for _ in range(plan.armhole_dec_rows):
        ops, new_count = paired_decreases(current, 1, 1)
        steps.append(
            build_step(
                number,
                current,
                ops,
                note_key="pattern.note.sleeve_cap",
            )
        )
        current = new_count
        number += 1
        steps.append(
            build_step(
                number,
                current,
                (Op(StitchKind.KNIT, times=current),),
            )
        )
        number += 1
    if current != plan.sleeve_cap_top:
        raise RuntimeError(
            f"manga {side}: termina con {current}, se esperaban {plan.sleeve_cap_top}"
        )
    return Section(
        id=f"sleeve_{side}",
        name_key=f"section.sleeve_{side}",
        mode="flat",
        steps=tuple(steps),
        start_stitches=plan.cuff_sts,
        end_stitches=current,
        target=SectionTarget(
            measurement_key=f"sleeve_{side}_length",
            target_cm=plan.sleeve_length_cm - CUFF_CM,
            tolerance_cm=1.0,
            dimension="length",
        ),
        meta={
            "row_count": plan.sleeve_body_rows + plan.sleeve_cap_rows,
            "cap_decreases": 2 * plan.armhole_dec_rows,
            "upper": plan.sleeve_upper_sts,
            "cap_top": plan.sleeve_cap_top,
        },
        bind_off=True,
    )


def _neckband(plan: SetInPlan) -> Section:
    rib = get_stitch("rib_1x1")
    steps: list[Step] = [
        build_step(
            1,
            0,
            (Op(StitchKind.CAST_ON, times=plan.neck_sts),),
            note_key="pattern.note.cast_on_panel",
        )
    ]
    for number in range(2, plan.neckband_rows + 2):
        steps.append(
            build_step(
                number,
                plan.neck_sts,
                expand_row(rib, plan.neck_sts, number - 1),
                note_key="pattern.note.neckband_sew" if number == 2 else None,
            )
        )
    return Section(
        id="neck_band",
        name_key="section.neckband",
        mode="flat",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=plan.neck_sts,
        target=SectionTarget(
            measurement_key="neckband_length",
            target_cm=NECKBAND_CM,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": plan.neckband_rows, "cast_on": plan.neck_sts},
        bind_off=True,
    )


def _warnings(
    spec: GarmentSpec, params: PatternParams, base_id: str
) -> tuple[Warning, ...]:
    warnings: list[Warning] = [
        Warning("gauge_sample", "warning.gauge_sample", severity="info"),
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", "warning.assumption", severity="info"),
        Warning("flat_panels", "warning.flat_panels"),
        Warning("no_neck_shaping", "warning.no_neck_shaping"),
        Warning("set_in_simplified", "warning.set_in_simplified"),
    ]
    if params.medidas_cm:
        warnings.append(
            Warning("custom_measurements", "warning.custom_measurements", severity="info")
        )
    if base_id != "stockinette":
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
    plan: SetInPlan, gauge: Gauge, size: BodySize
) -> tuple[Measurement, ...]:
    return (
        Measurement(
            key="bust",
            value_cm=gauge.cm_for_stitches(2 * plan.body_sts),
            target_cm=size.bust_cm + plan.ease,
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="circumference",
        ),
        Measurement(
            key="body_length",
            value_cm=gauge.cm_for_rows(plan.body_rows),
            target_cm=plan.body_length_cm,
            tolerance_cm=1.0,
            kind="length",
        ),
        Measurement(
            key="sleeve_length",
            value_cm=gauge.cm_for_rows(
                plan.cuff_rows + plan.sleeve_body_rows + plan.sleeve_cap_rows
            ),
            target_cm=plan.sleeve_length_cm,
            tolerance_cm=1.5,
            kind="length",
        ),
        Measurement(
            key="upper_arm",
            value_cm=gauge.cm_for_stitches(plan.sleeve_upper_sts),
            target_cm=size.upper_arm_cm + SLEEVE_EASE_CM,
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="circumference",
        ),
        Measurement(
            key="armhole",
            value_cm=gauge.cm_for_rows(plan.sleeve_cap_rows),
            target_cm=plan.armhole_cm,
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="length",
        ),
        Measurement(
            key="neck",
            value_cm=gauge.cm_for_stitches(plan.neck_sts),
            target_cm=size.neck_cm,
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="circumference",
        ),
    )


def generate_set_in(spec: GarmentSpec, params: PatternParams) -> Pattern:
    plan, gauge, size = plan_set_in(spec, params)
    base_id = catalog_id_for_name(spec.punto_base or StitchPatternName.STOCKINETTE)
    if base_id == "other":
        base_id = "stockinette"
    sections = (
        _body_panel("back", "section.back", plan),
        _body_panel("front", "section.front", plan),
        _sleeve("left", plan),
        _cuff("left", plan),
        _sleeve("right", plan),
        _cuff("right", plan),
        _neckband(plan),
    )
    body_area = (
        2
        * gauge.cm_for_stitches(plan.body_sts)
        * gauge.cm_for_rows(plan.body_rows)
    )
    sleeve_area = (
        2
        * gauge.cm_for_stitches(plan.sleeve_upper_sts)
        * gauge.cm_for_rows(plan.sleeve_body_rows + plan.sleeve_cap_rows)
    )
    band_area = gauge.cm_for_stitches(plan.neck_sts) * NECKBAND_CM
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
        family="set_in",
        title_key="title.pullover_set_in",
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
            label_key="join.side_seam",
            left=(CountRef("back", "end"),),
            right=(CountRef("front", "end"),),
        ),
        JoinCheck(
            label_key="join.shoulder_seam",
            left=(CountRef("back", "end"),),
            right=(CountRef("front", "end"),),
        ),
        JoinCheck(
            label_key="join.armhole",
            left=(
                CountRef("back", "meta:armhole_decreases"),
                CountRef("front", "meta:armhole_decreases"),
            ),
            right=(
                CountRef("sleeve_left", "meta:cap_decreases"),
                CountRef("sleeve_right", "meta:cap_decreases"),
            ),
        ),
        JoinCheck(
            label_key="join.cuff_left",
            left=(CountRef("sleeve_left", "start"),),
            right=(CountRef("cuff_left", "end"),),
        ),
        JoinCheck(
            label_key="join.cuff_right",
            left=(CountRef("sleeve_right", "start"),),
            right=(CountRef("cuff_right", "end"),),
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
