"""Prendas planas: hombro caido, cardigan y chaleco.

Se tejen en piezas rectangulares y se cosen. Esta primera version no modela
sisas, escotes ni ojales: esas limitaciones se declaran en las advertencias del
patron. El simulador verifica cada pieza y las costuras que se declaran.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from engine import ENGINE_VERSION
from engine.garments.base import ImpossibleProportionsError
from engine.garments.rows import FlatRows, hem_rib, rib_rows
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

BAND_CM = 4.0
NECKBAND_CM = 3.0
BUTTON_BAND_CM = 5.0
SLEEVE_EASE_CM = 4.0
MEASUREMENT_TOLERANCE_CM = 2.5


@dataclass(frozen=True)
class FlatPlan:
    kind: str
    back_sts: int
    front_sts: int
    front_each: int
    sleeve_sts: int | None
    total_sts: int
    body_rows: int
    sleeve_rows: int
    cuff_rows: int
    neck_sts: int
    neckband_rows: int
    band_sts: int
    band_rows: int
    body_length_cm: float
    sleeve_length_cm: float | None
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


def plan_flat(spec: GarmentSpec, params: PatternParams, kind: str) -> tuple[FlatPlan, Gauge, BodySize]:
    size = resolve_body_size(params.talla, params.medidas_cm)
    gauge = resolve_gauge(params)
    ease = params.ease_cm if params.ease_cm is not None else ease_for_fit(spec.ajuste)
    body_length_cm = _body_length_cm(spec, size)
    target_sts = (size.bust_cm + ease) * gauge.stitches_per_10cm / 10.0
    if kind == "cardigan":
        front_each = max(2, round_half_up(target_sts / 4))
        back = 2 * front_each
        total_sts = back + 2 * front_each
        front_sts = front_each
    else:
        back = max(2, round_half_up(target_sts / 2))
        front_sts = back
        total_sts = back + front_sts
        front_each = front_sts
    body_rows = max(1, gauge.rows_for_cm(body_length_cm))

    sleeve_sts: int | None = None
    sleeve_rows = 0
    cuff_rows = 0
    sleeve_length_cm: float | None = None
    if kind != "vest":
        sleeve_length_cm = _sleeve_length_cm(spec, size)
        if sleeve_length_cm <= BAND_CM + 2:
            raise ImpossibleProportionsError(
                "error.impossible_proportions",
                yoke=0,
                body=body_length_cm,
                sleeve=sleeve_length_cm,
            )
        sleeve_sts = adjust_stitches(
            max(4, gauge.stitches_for_cm(size.upper_arm_cm + SLEEVE_EASE_CM)),
            4,
            mode="nearest",
        )
        sleeve_rows = max(1, gauge.rows_for_cm(sleeve_length_cm - BAND_CM))
        cuff_rows = max(1, gauge.rows_for_cm(BAND_CM))

    neck_sts = adjust_stitches(
        max(4, gauge.stitches_for_cm(size.neck_cm + 2.0)), 4, mode="nearest"
    )
    neckband_rows = max(1, gauge.rows_for_cm(NECKBAND_CM))
    band_sts = adjust_stitches(
        max(4, gauge.stitches_for_cm(BUTTON_BAND_CM)), 2, mode="nearest"
    )
    plan = FlatPlan(
        kind=kind,
        back_sts=back,
        front_sts=front_sts,
        front_each=front_each,
        sleeve_sts=sleeve_sts,
        total_sts=total_sts,
        body_rows=body_rows,
        sleeve_rows=sleeve_rows,
        cuff_rows=cuff_rows,
        neck_sts=neck_sts,
        neckband_rows=neckband_rows,
        band_sts=band_sts,
        band_rows=body_rows,
        body_length_cm=body_length_cm,
        sleeve_length_cm=sleeve_length_cm,
        ease=ease,
    )
    return plan, gauge, size


def _panel_section(
    section_id: str,
    name_key: str,
    stitches: int,
    rows: int,
    target_cm: float,
    *,
    note_key: str | None = None,
    hem_rows: int = 0,
) -> Section:
    """Pieza plana en jersey (reves al reves), con elastico abajo si se pide."""
    flat = FlatRows(0)
    flat.add((Op(StitchKind.CAST_ON, times=stitches),), "pattern.note.cast_on_panel")
    hem = min(hem_rows, max(0, rows - 2))
    rib_rows(flat, hem_rib(stitches), hem, "pattern.note.hem")
    for index in range(rows - hem):
        flat.plain(note_key if index == 0 else None)
    return Section(
        id=section_id,
        name_key=name_key,
        mode="flat",
        steps=tuple(flat.steps),
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


def _rib_section(
    section_id: str,
    name_key: str,
    stitches: int,
    rows: int,
    pattern_id: str,
    target_cm: float,
    *,
    note_key: str | None = None,
) -> Section:
    rib = get_stitch(pattern_id)
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
                expand_row(rib, stitches, number - 1),
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


def _sections(plan: FlatPlan, gauge: Gauge) -> tuple[Section, ...]:
    sections: list[Section] = [
        _panel_section(
            "back",
            "section.back",
            plan.back_sts,
            plan.body_rows,
            plan.body_length_cm,
            note_key="pattern.note.flat_panel",
            hem_rows=plan.cuff_rows or max(2, plan.neckband_rows),
        )
    ]
    if plan.kind == "cardigan":
        for side, name in (("left", "section.left_front"), ("right", "section.right_front")):
            sections.append(
                _panel_section(
                    f"{side}_front",
                    name,
                    plan.front_each,
                    plan.body_rows,
                    plan.body_length_cm,
                    note_key="pattern.note.flat_panel",
                    hem_rows=plan.cuff_rows or max(2, plan.neckband_rows),
                )
            )
    else:
        sections.append(
            _panel_section(
                "front",
                "section.front",
                plan.front_sts,
                plan.body_rows,
                plan.body_length_cm,
                note_key="pattern.note.flat_panel",
                hem_rows=plan.cuff_rows or max(2, plan.neckband_rows),
            )
        )

    if plan.sleeve_sts is not None:
        for side in ("left", "right"):
            sections.append(
                _panel_section(
                    f"sleeve_{side}",
                    f"section.sleeve_{side}",
                    plan.sleeve_sts,
                    plan.sleeve_rows,
                    (plan.sleeve_length_cm or 0.0) - BAND_CM,
                    note_key="pattern.note.flat_panel",
                )
            )
            sections.append(
                _rib_section(
                    f"cuff_{side}",
                    "section.cuff",
                    plan.sleeve_sts,
                    plan.cuff_rows,
                    "rib_2x2",
                    BAND_CM,
                    note_key="pattern.note.cuff",
                )
            )

    sections.append(
        _rib_section(
            "neckband",
            "section.neckband",
            plan.neck_sts,
            plan.neckband_rows,
            "rib_1x1",
            NECKBAND_CM,
            note_key="pattern.note.neckband_sew",
        )
    )
    if plan.kind == "cardigan":
        for side in ("left", "right"):
            sections.append(
                _rib_section(
                    f"button_band_{side}",
                    "section.button_band",
                    plan.band_sts,
                    plan.band_rows,
                    "garter",
                    plan.body_length_cm,
                    note_key="pattern.note.button_band",
                )
            )
    return tuple(sections)


def _warnings(
    spec: GarmentSpec,
    params: PatternParams,
    plan: FlatPlan,
    base_id: str,
) -> tuple[Warning, ...]:
    warnings: list[Warning] = [
        Warning("gauge_sample", "warning.gauge_sample", severity="info"),
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", "warning.assumption", severity="info"),
        Warning("flat_panels", "warning.flat_panels"),
        Warning("no_neck_shaping", "warning.no_neck_shaping"),
    ]
    if plan.kind == "cardigan":
        warnings.append(Warning("no_buttonholes", "warning.no_buttonholes"))
    if plan.kind == "vest":
        warnings.append(Warning("vest_armhole", "warning.vest_armhole"))
    if plan.ease < 0:
        warnings.append(Warning("negative_ease", "warning.negative_ease"))
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
    plan: FlatPlan, gauge: Gauge, size: BodySize
) -> tuple[Measurement, ...]:
    measurements = [
        Measurement(
            key="bust",
            value_cm=gauge.cm_for_stitches(plan.total_sts),
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
            key="neck",
            value_cm=gauge.cm_for_stitches(plan.neck_sts),
            target_cm=size.neck_cm + 2.0,
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="circumference",
        ),
    ]
    if plan.sleeve_sts is not None and plan.sleeve_length_cm is not None:
        measurements.extend(
            [
                Measurement(
                    key="sleeve_length",
                    value_cm=gauge.cm_for_rows(plan.sleeve_rows + plan.cuff_rows),
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
            ]
        )
    return tuple(measurements)


def _joins(plan: FlatPlan) -> tuple[JoinCheck, ...]:
    joins: list[JoinCheck] = []
    if plan.kind == "cardigan":
        joins.append(
            JoinCheck(
                label_key="join.side_seam",
                left=(CountRef("back", "end"),),
                right=(CountRef("left_front", "end"), CountRef("right_front", "end")),
            )
        )
    else:
        joins.append(
            JoinCheck(
                label_key="join.side_seam",
                left=(CountRef("back", "end"),),
                right=(CountRef("front", "end"),),
            )
        )
    if plan.sleeve_sts is not None:
        for side in ("left", "right"):
            joins.append(
                JoinCheck(
                    label_key=f"join.cuff_{side}",
                    left=(CountRef(f"sleeve_{side}", "end"),),
                    right=(CountRef(f"cuff_{side}", "meta:cast_on"),),
                )
            )
    return tuple(joins)


def generate_flat(
    spec: GarmentSpec, params: PatternParams, kind: str
) -> Pattern:
    plan, gauge, size = plan_flat(spec, params, kind)
    base_id = catalog_id_for_name(spec.punto_base or StitchPatternName.STOCKINETTE)
    if base_id == "other":
        base_id = "stockinette"
    sections = _sections(plan, gauge)

    body_area = (
        gauge.cm_for_stitches(plan.total_sts)
        * gauge.cm_for_rows(plan.body_rows)
    )
    sleeve_area = 0.0
    if plan.sleeve_sts is not None:
        sleeve_area = (
            2
            * gauge.cm_for_stitches(plan.sleeve_sts)
            * gauge.cm_for_rows(plan.sleeve_rows + plan.cuff_rows)
        )
    band_area = gauge.cm_for_stitches(plan.neck_sts) * NECKBAND_CM
    if plan.kind == "cardigan":
        band_area += 2 * gauge.cm_for_stitches(plan.band_sts) * gauge.cm_for_rows(
            plan.band_rows
        )
    meters, grams = estimate_yarn(body_area + sleeve_area + band_area, params.peso_hilo)
    notions = (
        "notion.stitch_markers",
        "notion.tapestry_needle",
        "notion.row_counter",
        "notion.tape_measure",
    )
    colors = tuple(spec.colorwork.paleta) if spec.colorwork else ()
    digest = hashlib.sha256(
        (spec.model_dump_json() + params.model_dump_json() + kind).encode("utf-8")
    ).hexdigest()[:12]
    title_key = {
        "drop_shoulder": "title.pullover_drop_shoulder",
        "cardigan": "title.cardigan",
        "vest": "title.vest",
    }[kind]
    meta = PatternMeta(
        id=digest,
        family=kind,
        title_key=title_key,
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
    return Pattern(
        meta=meta,
        spec=spec,
        params=params,
        sections=sections,
        measurements=_measurements(plan, gauge, size),
        materials=materials,
        warnings=_warnings(spec, params, plan, base_id),
        joins=_joins(plan),
    )
