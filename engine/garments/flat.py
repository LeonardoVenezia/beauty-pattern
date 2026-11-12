"""Prendas planas: hombro caido, cardigan y chaleco.

Se tejen en piezas rectangulares y se cosen. Esta primera version no modela
sisas, escotes ni ojales: esas limitaciones se declaran en las advertencias del
patron. El simulador verifica cada pieza y las costuras que se declaran.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from engine import ENGINE_VERSION
from engine.garments.base import ImpossibleProportionsError
from engine.garments.panels import build_panel, compensation, texture_motif
from engine.garments.rows import (
    FlatRows,
    front_neck_rows,
    neck_sections,
    neckband_stitches,
    plan_crew_neck,
    rib_rows,
)
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
    neck_center: int
    neck: tuple[int, int, int] | None  # (hileras, disminuciones, cierre central)
    # Cardigan: (hileras, cierre en el borde, disminuciones, en V) por delantero.
    front_neck: tuple[int, int, int, bool] | None
    neckband_sts: int
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


V_NECK_STYLES_CREW = {Neckline.CREW, Neckline.TURTLENECK, Neckline.FUNNEL}


def _plan_front_neck(
    spec: GarmentSpec, size: BodySize, gauge: Gauge, neck_center: int, rows_available: int
) -> tuple[int, int, int, bool] | None:
    """Escote de cada delantero del cardigan: en V (por defecto) o redondo.

    Cada delantero pierde la mitad del escote de la espalda, asi el hombro
    coincide con el de la espalda. ASUNCION: la V empieza a la altura de la
    sisa (profundidad = sisa del talle); el redondo usa `plan_crew_neck`.
    """
    half = neck_center // 2
    if spec.escote in V_NECK_STYLES_CREW:
        try:
            depth, decs, _center = plan_crew_neck(neck_center, rows_available, gauge.rows_per_cm)
        except ValueError:
            return None
        return depth, half - decs, decs, False
    depth = min(gauge.rows_for_cm(size.armhole_cm), rows_available)
    if half < 1 or 2 * half > depth:
        return None
    return depth, 0, half, True


def plan_flat(spec: GarmentSpec, params: PatternParams, kind: str) -> tuple[FlatPlan, Gauge, BodySize]:
    size = resolve_body_size(params.talla, params.medidas_cm)
    gauge = resolve_gauge(params)
    ease = params.ease_cm if params.ease_cm is not None else ease_for_fit(spec.ajuste)
    body_length_cm = _body_length_cm(spec, size)
    target_sts = (size.bust_cm + ease) * gauge.stitches_per_10cm / 10.0
    if kind == "cardigan":
        # Par, para que el elastico del borde entre justo en cada delantero.
        front_each = max(2, round_half_up(target_sts / 4))
        even = 2 * round_half_up(target_sts / 8)
        # Par (el elastico entra justo) si no aleja el contorno mas de 1,5 cm.
        if abs(4 * even - target_sts) <= 1.5 * gauge.stitches_per_cm:
            front_each = max(2, even)
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
    # Escote redondo en el delantero (pullover y chaleco); el cardigan lleva
    # el escote en cada delantero (`_plan_front_neck`).
    neck_center = min(adjust_stitches(max(4, neck_sts // 2), 2, mode="nearest"), front_sts - 8)
    neck_center -= (front_sts - neck_center) % 2
    neck_plan: tuple[int, int, int] | None = None
    front_neck: tuple[int, int, int, bool] | None = None
    neckband_sts = neck_sts
    if kind == "cardigan":
        neck_center = adjust_stitches(max(4, neck_sts // 2), 2, mode="nearest")
        front_neck = _plan_front_neck(spec, size, gauge, neck_center, body_rows - (cuff_rows or 2) - 2)
        if front_neck is not None:
            neckband_sts = neckband_stitches(neck_center, 2 * front_neck[1], front_neck[0])
    else:
        hem = cuff_rows or max(2, neckband_rows)
        try:
            neck_plan = plan_crew_neck(neck_center, body_rows - hem - 2, gauge.rows_per_cm)
        except ValueError:
            neck_plan = None
        if neck_plan is not None:
            neckband_sts = neckband_stitches(neck_center, neck_plan[2], neck_plan[0])
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
        neck_center=neck_center,
        neck=neck_plan,
        front_neck=front_neck,
        neckband_sts=neckband_sts,
        neckband_rows=neckband_rows,
        band_sts=band_sts,
        band_rows=body_rows - (front_neck[0] if front_neck else 0),
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
    spec: GarmentSpec | None = None,
    neck: tuple[int, int, int] | None = None,
    params: PatternParams | None = None,
    front_neck: tuple[int, int, int, bool] | None = None,
    neck_at_start: bool = False,
) -> tuple[Section, ...]:
    """Pieza plana en jersey (reves al reves), con elastico abajo si se pide.

    Si la foto tiene textura, el cuerpo lleva un panel centrado (`panels`).
    """
    flat = FlatRows(0)
    flat.add((Op(StitchKind.CAST_ON, times=stitches),), "pattern.note.cast_on_panel")
    hem = min(hem_rows, max(0, rows - 2))
    rib_rows(flat, hem, "pattern.note.hem")
    motif = texture_motif(spec) if spec is not None else None
    # En un delantero con escote, el panel va centrado en la parte del hombro
    # para que las disminuciones del escote nunca lo alcancen.
    neck_sts = (front_neck[1] + front_neck[2]) if front_neck else 0
    panel = build_panel(motif, stitches - neck_sts) if motif else None
    panel_start = len(flat.steps)
    if panel is not None:
        comp = 0
        if params is not None and rows - hem > 6:
            comp = compensation(panel, resolve_gauge(params).stitches_per_cm, params.panel_motivo_cm)
        offset = None
        if front_neck:
            offset = (stitches - neck_sts - panel.width) // 2 + (neck_sts if neck_at_start else 0)
        flat.start_panel(panel, comp, left=offset)
    shaped = neck[0] if neck else (front_neck[0] if front_neck else 0)
    target = rows - shaped  # hileras antes del escote o del cierre
    while len(flat.steps) - 1 < target:
        done = len(flat.steps) - 1
        if flat.extra and not flat.pending_increase and target - done <= 2:
            # Los pts de compensacion se quitan antes del escote o del cierre.
            flat.remove_compensation()
            continue
        flat.row(note=note_key if done == hem and panel is None else None)
    extra = flat.panel_meta(panel_start, stitches)
    if front_neck is not None:
        depth, bind_off, decs, spread = front_neck
        front_neck_rows(flat, depth, bind_off, decs, neck_at_start=neck_at_start, spread=spread)
        return (Section(
            id=section_id,
            name_key=name_key,
            mode="flat",
            steps=tuple(flat.steps),
            start_stitches=0,
            end_stitches=flat.current,
            target=SectionTarget(
                measurement_key=f"{section_id}_length",
                target_cm=target_cm,
                tolerance_cm=0.5,
                dimension="length",
            ),
            meta={"row_count": rows, "cast_on": stitches, "neck_rows": depth, **extra},
            bind_off=True,
        ),)
    if neck is not None:
        _depth, decs, center_bo = neck
        before, after = flat.split_for_neck(center_bo, "pattern.note.neck_split")
        side_rows = rows - (len(flat.steps) - 1)
        shoulder = (stitches - center_bo) // 2 - decs
        sides = neck_sections(before, after, decs, side_rows, shoulder)
        front = Section(
            id=section_id,
            name_key=name_key,
            mode="flat",
            steps=tuple(flat.steps),
            start_stitches=0,
            end_stitches=flat.current,
            target=SectionTarget(
                measurement_key=f"{section_id}_length",
                target_cm=target_cm * (len(flat.steps) - 1) / rows,
                tolerance_cm=0.5,
                dimension="length",
            ),
            meta={"row_count": len(flat.steps) - 1, "cast_on": stitches, **extra},
        )
        return (front, *sides)
    return (Section(
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
        meta={"row_count": rows, "cast_on": stitches, **extra},
        bind_off=True,
    ),)


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


def _sections(plan: FlatPlan, gauge: Gauge, spec: GarmentSpec, params: PatternParams) -> tuple[Section, ...]:
    hem = plan.cuff_rows or max(2, plan.neckband_rows)
    sections: list[Section] = [
        *_panel_section(
            "back",
            "section.back",
            plan.back_sts,
            plan.body_rows,
            plan.body_length_cm,
            note_key="pattern.note.flat_panel",
            hem_rows=hem,
            spec=spec,
            params=params,
        )
    ]
    if plan.neck is not None or plan.front_neck is not None:
        # Costura de hombro: la espalda deja libres los pts del escote.
        back = sections[0]
        shoulder = (plan.back_sts - plan.neck_center) // 2
        sections[0] = replace(back, meta={**back.meta, "shoulder": shoulder})
    if plan.kind == "cardigan":
        for side, name in (("left", "section.left_front"), ("right", "section.right_front")):
            sections.extend(
                _panel_section(
                    f"{side}_front",
                    name,
                    plan.front_each,
                    plan.body_rows,
                    plan.body_length_cm,
                    note_key="pattern.note.flat_panel",
                    hem_rows=hem,
                    spec=spec,
                    params=params,
                    front_neck=plan.front_neck,
                    # Delantero derecho: el borde del medio esta al comienzo
                    # de las hileras del LD.
                    neck_at_start=side == "right",
                )
            )
    else:
        sections.extend(
            _panel_section(
                "front",
                "section.front",
                plan.front_sts,
                plan.body_rows,
                plan.body_length_cm,
                note_key="pattern.note.flat_panel",
                hem_rows=hem,
                spec=spec,
                neck=plan.neck,
                params=params,
            )
        )

    if plan.sleeve_sts is not None:
        for side in ("left", "right"):
            sections.extend(
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
            plan.neckband_sts,
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
                    f"section.button_band_{side}",
                    plan.band_sts,
                    plan.band_rows,
                    "garter",
                    plan.body_length_cm * plan.band_rows / plan.body_rows,
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
    ]
    if plan.neck is None and plan.front_neck is None:
        warnings.append(Warning("no_neck_shaping", "warning.no_neck_shaping"))
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
    motif = texture_motif(spec)
    if motif is not None:
        warnings.append(
            Warning(
                "texture_panel",
                "warning.texture_panel_compensated" if params.panel_motivo_cm else "warning.texture_panel_flat",
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
    if plan.kind == "cardigan" and plan.front_neck is not None:
        joins.append(
            JoinCheck(
                label_key="join.side_seam",
                left=(CountRef("back", "meta:cast_on"),),
                right=(CountRef("left_front", "meta:cast_on"), CountRef("right_front", "meta:cast_on")),
            )
        )
        for side in ("left_front", "right_front"):
            joins.append(
                JoinCheck(
                    label_key="join.shoulder_seam",
                    left=(CountRef("back", "meta:shoulder"),),
                    right=(CountRef(side, "end"),),
                )
            )
    elif plan.kind == "cardigan":
        joins.append(
            JoinCheck(
                label_key="join.side_seam",
                left=(CountRef("back", "end"),),
                right=(CountRef("left_front", "end"), CountRef("right_front", "end")),
            )
        )
    elif plan.neck is not None:
        joins.append(
            JoinCheck(
                label_key="join.side_seam",
                left=(CountRef("back", "meta:cast_on"),),
                right=(CountRef("front", "meta:cast_on"),),
            )
        )
        for side in ("neck_right", "neck_left"):
            joins.append(
                JoinCheck(
                    label_key="join.shoulder_seam",
                    left=(CountRef("back", "meta:shoulder"),),
                    right=(CountRef(side, "end"),),
                )
            )
        joins.append(
            JoinCheck(
                label_key="join.neck_split",
                left=(CountRef("front", "end"),),
                right=(CountRef("neck_right", "start"), CountRef("neck_left", "start")),
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
    sections = _sections(plan, gauge, spec, params)

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
