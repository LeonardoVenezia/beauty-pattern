"""Pullover con manga encajada, tejido en piezas planas.

Construccion clasica de abajo hacia arriba: elastico, jersey, sisa con
cierre y disminuciones hasta el ancho de espalda, copa de manga estandar.
El escote es recto (los pts centrales quedan libres al coser los hombros);
se declara en las advertencias.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from engine import ENGINE_VERSION
from engine.distribution import regular_rows
from engine.garments.base import ImpossibleProportionsError
from engine.garments.rows import FlatRows as _Rows
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
    hem_rows: int
    underarm_rows: int  # jersey desde el elastico hasta la sisa
    armhole_bo: int  # pts cerrados al inicio de cada una de las 2 hileras
    armhole_decs: int  # disminuciones por lado, en hileras del LD
    armhole_rows: int
    cross_sts: int  # ancho de espalda en los hombros
    neck_center: int  # pts centrales que quedan libres para el escote
    cuff_sts: int
    cuff_rows: int
    sleeve_upper_sts: int
    sleeve_body_rows: int
    sleeve_incs: int  # aumentos por lado
    cap_decs: int  # disminuciones por lado en la copa
    cap_rows: int
    cap_top: int  # pts que se cierran al final de la copa
    neck_sts: int  # pts del cuello (tira)
    neckband_rows: int
    body_length_cm: float
    sleeve_length_cm: float
    armhole_cm: float
    ease: float

    @property
    def body_rows(self) -> int:
        return self.hem_rows + self.underarm_rows + self.armhole_rows


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


def _even(value: float) -> int:
    return max(2, round_half_up(value / 2.0) * 2)


def plan_set_in(
    spec: GarmentSpec, params: PatternParams
) -> tuple[SetInPlan, Gauge, BodySize]:
    """Manga encajada clasica, de abajo hacia arriba en piezas.

    Sisa: se cierran pts al inicio de las 2 hileras siguientes (ASUNCION: 40 %
    de lo que hay que quitar por lado) y el resto con 1 disminucion por lado
    en cada hilera del LD, hasta el ancho de espalda de la tabla; despues
    recto hasta la profundidad de sisa. Copa: mismo cierre que la sisa,
    disminuciones en hileras del LD, 2 pts cerrados al inicio de las 4
    hileras siguientes y cierre del resto. Alto de copa: 65 % de la sisa
    (ASUNCION). Ver docs/fuentes.md.
    """
    size = resolve_body_size(params.talla, params.medidas_cm)
    gauge = resolve_gauge(params)
    ease = params.ease_cm if params.ease_cm is not None else ease_for_fit(spec.ajuste)
    body_length_cm = _body_length_cm(spec, size)
    sleeve_length_cm = _sleeve_length_cm(spec, size)
    armhole_cm = size.armhole_cm

    def fail() -> ImpossibleProportionsError:
        return ImpossibleProportionsError(
            "error.impossible_proportions",
            yoke=round(armhole_cm, 1),
            body=body_length_cm,
            sleeve=sleeve_length_cm,
        )

    body_sts = max(8, _even((size.bust_cm + ease) * gauge.stitches_per_cm / 2.0))
    cross_sts = min(_even(size.cross_back_cm * gauge.stitches_per_cm), body_sts - 4)
    per_side = (body_sts - cross_sts) // 2
    cross_sts = body_sts - 2 * per_side
    armhole_bo = max(1, round_half_up(per_side * 0.4)) if per_side else 0
    armhole_decs = per_side - armhole_bo
    armhole_rows = max(2 + 2 * armhole_decs, gauge.rows_for_cm(armhole_cm))
    hem_rows = max(2, gauge.rows_for_cm(CUFF_CM))
    underarm_rows = gauge.rows_for_cm(body_length_cm) - hem_rows - armhole_rows
    if underarm_rows < 2:
        raise fail()
    neck_sts = _even(size.neck_cm * gauge.stitches_per_cm / 2.0)
    neck_center = min(neck_sts, cross_sts - 4)
    if (cross_sts - neck_center) % 2:
        neck_center -= 1

    cuff_sts = max(4, round_half_up((size.wrist_cm + CUFF_EASE_CM) * gauge.stitches_per_cm / 4.0) * 4)
    sleeve_upper_sts = _even((size.upper_arm_cm + SLEEVE_EASE_CM) * gauge.stitches_per_cm)
    if sleeve_upper_sts <= cuff_sts:
        sleeve_upper_sts = cuff_sts + 2
    sleeve_incs = (sleeve_upper_sts - cuff_sts) // 2
    sleeve_upper_sts = cuff_sts + 2 * sleeve_incs
    cuff_rows = max(2, gauge.rows_for_cm(CUFF_CM))
    cap_cm = armhole_cm * 0.65
    cap_rows = max(8, gauge.rows_for_cm(cap_cm))
    sleeve_body_cm = sleeve_length_cm - CUFF_CM - cap_cm
    sleeve_body_rows = gauge.rows_for_cm(sleeve_body_cm)
    if sleeve_body_rows < 2:
        raise fail()
    # Copa: 2 hileras de cierre de sisa + disminuciones (LD) + 4 hileras de
    # cierre de 2 pts; arriba quedan entre 5 y 8 cm.
    top_target = _even(6.5 * gauge.stitches_per_cm)
    after_bo = sleeve_upper_sts - 2 * armhole_bo - 8
    middle_rows = cap_rows - 2 - 4
    cap_decs = max(0, min((after_bo - top_target) // 2, middle_rows // 2))
    cap_top = after_bo - 2 * cap_decs
    if cap_top < 2:
        raise fail()
    if 2 * sleeve_incs > sleeve_body_rows:
        # Manga corta: no hay largo para llegar desde la muneca; el puno se
        # teje mas ancho, cerca del contorno del brazo.
        sleeve_incs = sleeve_body_rows // 2
        cuff_sts = sleeve_upper_sts - 2 * sleeve_incs

    plan = SetInPlan(
        body_sts=body_sts,
        hem_rows=hem_rows,
        underarm_rows=underarm_rows,
        armhole_bo=armhole_bo,
        armhole_decs=armhole_decs,
        armhole_rows=armhole_rows,
        cross_sts=cross_sts,
        neck_center=neck_center,
        cuff_sts=cuff_sts,
        cuff_rows=cuff_rows,
        sleeve_upper_sts=sleeve_upper_sts,
        sleeve_body_rows=sleeve_body_rows,
        sleeve_incs=sleeve_incs,
        cap_decs=cap_decs,
        cap_rows=2 + middle_rows + 4,
        cap_top=cap_top,
        neck_sts=2 * neck_center,
        neckband_rows=max(1, gauge.rows_for_cm(NECKBAND_CM)),
        body_length_cm=body_length_cm,
        sleeve_length_cm=sleeve_length_cm,
        armhole_cm=armhole_cm,
        ease=ease,
    )
    return plan, gauge, size


def _body_panel(section_id: str, name_key: str, plan: SetInPlan) -> Section:
    rib = get_stitch("rib_2x2" if plan.body_sts % 4 == 0 else "rib_1x1")
    rows = _Rows(0)
    rows.add((Op(StitchKind.CAST_ON, times=plan.body_sts),), "pattern.note.cast_on_panel")
    for index in range(plan.hem_rows):
        rows.add(expand_row(rib, plan.body_sts, index + 1), "pattern.note.hem" if index == 0 else None)
    for index in range(plan.underarm_rows):
        rows.plain("pattern.note.flat_panel" if index == 0 else None)
    armhole_start = len(rows.steps)
    if plan.armhole_bo:
        if not rows.right_side:
            rows.plain()
        rows.bind_off_start(plan.armhole_bo, "pattern.note.armhole_shaping")
        rows.bind_off_start(plan.armhole_bo)
    for _ in range(plan.armhole_decs):
        rows.decrease_edges("pattern.note.armhole_decrease")
        rows.plain()
    while len(rows.steps) - armhole_start < plan.armhole_rows:
        rows.plain()
    if rows.current != plan.cross_sts:
        raise RuntimeError(f"{section_id}: termina con {rows.current}, se esperaban {plan.cross_sts}")
    return Section(
        id=section_id,
        name_key=name_key,
        mode="flat",
        steps=tuple(rows.steps),
        start_stitches=0,
        end_stitches=rows.current,
        target=SectionTarget(
            measurement_key=f"{section_id}_length",
            target_cm=plan.body_length_cm,
            tolerance_cm=1.0,
            dimension="length",
        ),
        meta={
            "row_count": len(rows.steps) - 1,
            "cast_on": plan.body_sts,
            "armhole_bo": plan.armhole_bo,
            "shoulder": (plan.cross_sts - plan.neck_center) // 2,
            "neck_center": plan.neck_center,
        },
        bind_off=True,
    )


def _cuff(side: str, plan: SetInPlan) -> Section:
    rib = get_stitch("rib_2x2" if plan.cuff_sts % 4 == 0 else "rib_1x1")
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
    )


def _sleeve(side: str, plan: SetInPlan) -> Section:
    """Manga desde el puno: aumentos en los bordes en hileras del LD y copa."""
    rows = _Rows(plan.cuff_sts)
    half = plan.sleeve_body_rows // 2
    increase_at = {2 * r - 1 for r in regular_rows(half, plan.sleeve_incs)} if plan.sleeve_incs else set()
    for index in range(plan.sleeve_body_rows):
        note = "pattern.note.flat_panel" if index == 0 else None
        if index + 1 in increase_at:
            rows.increase_edges("pattern.note.sleeve_increase")
        else:
            rows.plain(note)
    if rows.current != plan.sleeve_upper_sts:
        raise RuntimeError(f"manga {side}: {rows.current} != {plan.sleeve_upper_sts}")
    cap_start = len(rows.steps)
    if not rows.right_side:
        rows.plain()
        cap_start = len(rows.steps)
    rows.bind_off_start(plan.armhole_bo, "pattern.note.sleeve_cap")
    rows.bind_off_start(plan.armhole_bo)
    for _ in range(plan.cap_decs):
        rows.decrease_edges("pattern.note.cap_decrease")
        rows.plain()
    while len(rows.steps) - cap_start < plan.cap_rows - 4:
        rows.plain()
    for index in range(4):
        rows.bind_off_start(2, "pattern.note.cap_top" if index == 0 else None)
    if rows.current != plan.cap_top:
        raise RuntimeError(f"manga {side}: copa termina con {rows.current}, se esperaban {plan.cap_top}")
    return Section(
        id=f"sleeve_{side}",
        name_key=f"section.sleeve_{side}",
        mode="flat",
        steps=tuple(rows.steps),
        start_stitches=plan.cuff_sts,
        end_stitches=rows.current,
        target=SectionTarget(
            measurement_key=f"sleeve_{side}_length",
            target_cm=plan.sleeve_length_cm - CUFF_CM,
            tolerance_cm=1.5,
            dimension="length",
        ),
        meta={
            "row_count": len(rows.steps),
            "armhole_bo": plan.armhole_bo,
            "cap_top": plan.cap_top,
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
    tol = MEASUREMENT_TOLERANCE_CM
    return (
        Measurement("bust", gauge.cm_for_stitches(2 * plan.body_sts), size.bust_cm + plan.ease, tol, "circumference"),
        Measurement("body_length", gauge.cm_for_rows(plan.body_rows), plan.body_length_cm, 1.5, "length"),
        Measurement(
            "sleeve_length",
            gauge.cm_for_rows(plan.cuff_rows + plan.sleeve_body_rows + plan.cap_rows),
            plan.sleeve_length_cm,
            2.0,
            "length",
        ),
        Measurement("upper_arm", gauge.cm_for_stitches(plan.sleeve_upper_sts), size.upper_arm_cm + SLEEVE_EASE_CM, tol, "circumference"),
        Measurement(
            "cross_back",
            gauge.cm_for_stitches(plan.cross_sts),
            min(size.cross_back_cm, gauge.cm_for_stitches(plan.body_sts - 4)),
            tol,
            "width",
        ),
        Measurement("armhole", gauge.cm_for_rows(plan.armhole_rows), plan.armhole_cm, 1.5, "length"),
        Measurement("neck", gauge.cm_for_stitches(plan.neck_sts), size.neck_cm, tol, "circumference"),
    )


def generate_set_in(spec: GarmentSpec, params: PatternParams) -> Pattern:
    plan, gauge, size = plan_set_in(spec, params)
    base_id = catalog_id_for_name(spec.punto_base or StitchPatternName.STOCKINETTE)
    if base_id == "other":
        base_id = "stockinette"
    sections = (
        _body_panel("back", "section.back", plan),
        _body_panel("front", "section.front", plan),
        _cuff("left", plan),
        _sleeve("left", plan),
        _cuff("right", plan),
        _sleeve("right", plan),
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
        * gauge.cm_for_rows(plan.sleeve_body_rows + plan.cap_rows)
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
            label_key="join.shoulder_seam",
            left=(CountRef("back", "end"),),
            right=(CountRef("front", "end"),),
        ),
        JoinCheck(
            label_key="join.armhole",
            left=(CountRef("back", "meta:armhole_bo"),),
            right=(CountRef("sleeve_left", "meta:armhole_bo"),),
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
