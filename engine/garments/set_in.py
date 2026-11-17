"""Pullover con manga encajada, tejido en piezas planas.

Construccion clasica de abajo hacia arriba: elastico, jersey, sisa con
cierre y disminuciones hasta el ancho de espalda, copa de manga estandar.
Escote redondo en el delantero (cierre central y cada hombro por separado);
la espalda termina recta.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from engine import ENGINE_VERSION
from engine.distribution import regular_rows
from engine.garments.base import ImpossibleProportionsError
from engine.garments.necklines import Placket, placket_band, placket_sides, plan_placket
from engine.garments.options import body_length_cm as _body_length_cm
from engine.garments.options import (
    effective_sleeve,
    has_sleeves,
    hem_circumference_cm,
    neck_cm,
    neck_depth_cm,
    neckband_cm,
    sleeve_style,
)
from engine.garments.options import sleeve_length_cm as _sleeve_length_cm
from engine.garments.panels import build_panel, compensation, texture_motif
from engine.garments.rows import FlatRows as _Rows
from engine.garments.rows import neck_sections, neckband_stitches, plan_crew_neck
from engine.garments.sleeves import (
    CAP_BAND_CM,
    bell_width,
    gather_rounds,
    puff_width,
    spread_decreases,
    spread_increases,
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
    Category,
    GarmentSpec,
    Neckline,
    PatternParams,
    Shape,
    SleeveLength,
    SleeveStyle,
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
ARMHOLE_BAND_CM = 2.5  # ASUNCION: tira de sisa de la musculosa


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
    neck_depth_rows: int  # hileras desde el cierre del escote hasta el hombro
    neck_decs: int  # disminuciones por lado en el escote
    neck_center_bo: int  # pts centrales que se cierran en el delantero
    neck_sts: int  # pts del cuello (tira)
    neckband_rows: int
    body_length_cm: float
    sleeve_length_cm: float
    armhole_cm: float
    ease: float
    hem_sts: int = 0  # ancho montado de cada pieza (vestido, linea A)
    sleeves: bool = True
    armhole_band_sts: int = 0  # sin mangas: tira de cada sisa
    armhole_band_rows: int = 0
    neckband_cm: float = NECKBAND_CM
    placket: Placket | None = None
    sleeve_style: SleeveStyle = SleeveStyle.STRAIGHT
    puff_sts: int = 0
    cuff_cm: float = CUFF_CM

    @property
    def body_rows(self) -> int:
        return self.hem_rows + self.underarm_rows + self.armhole_rows


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
    sleeves = has_sleeves(spec)
    sleeve_length_cm = _sleeve_length_cm(spec, size) if sleeves else 0.0
    armhole_cm = size.armhole_cm
    style = sleeve_style(spec) if sleeves else SleeveStyle.STRAIGHT

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
    neck_sts = _even(neck_cm(spec, size) * gauge.stitches_per_cm / 2.0)
    neck_center = min(neck_sts, cross_sts - 4)
    if (cross_sts - neck_center) % 2:
        neck_center -= 1

    shaping_rows = 3 + 2 * armhole_decs
    try:
        neck_depth_rows, neck_decs, _ = plan_crew_neck(
            neck_center, armhole_rows - shaping_rows - 2, gauge.rows_per_cm, neck_depth_cm(spec)
        )
    except ValueError:
        raise fail() from None
    neckband_sts = neckband_stitches(neck_center, neck_center - 2 * neck_decs, neck_depth_rows)
    placket = None
    if spec.escote in {Neckline.HENLEY, Neckline.POLO}:
        placket = plan_placket(
            gauge, neck_center - 2 * neck_decs, armhole_rows - shaping_rows - neck_depth_rows - 3
        )
    # Vestido y linea A: se monta el ancho del borde y se disminuye en los
    # costados antes de la sisa.
    flare_target = hem_circumference_cm(spec, size, ease) * gauge.stitches_per_cm / 2.0
    flare = max(0, round_half_up((flare_target - body_sts) / 2))
    flare = min(flare, max(0, (underarm_rows - 8) // 2))
    hem_sts = body_sts + 2 * flare

    kind = effective_sleeve(spec)
    cuff_cm_target = size.wrist_cm + CUFF_EASE_CM
    if kind is SleeveLength.ELBOW or (style is SleeveStyle.PUFF and kind is SleeveLength.SHORT):
        # ASUNCION: en el codo, el promedio entre muneca y brazo.
        cuff_cm_target = (size.wrist_cm + size.upper_arm_cm) / 2 + CUFF_EASE_CM
    cuff_sts = max(4, round_half_up(cuff_cm_target * gauge.stitches_per_cm / 4.0) * 4)
    sleeve_upper_sts = _even((size.upper_arm_cm + SLEEVE_EASE_CM) * gauge.stitches_per_cm)
    if sleeve_upper_sts <= cuff_sts:
        sleeve_upper_sts = cuff_sts + 2
    sleeve_incs = (sleeve_upper_sts - cuff_sts) // 2
    sleeve_upper_sts = cuff_sts + 2 * sleeve_incs
    cuff_cm = CAP_BAND_CM if style is SleeveStyle.CAP else CUFF_CM
    cuff_rows = max(2, gauge.rows_for_cm(cuff_cm))
    cap_cm = armhole_cm * 0.65
    cap_rows = max(8, gauge.rows_for_cm(cap_cm))
    if style is SleeveStyle.CAP:
        # Casquillo: la tira y enseguida la copa, sin aumentos.
        sleeve_length_cm = cuff_cm + gauge.cm_for_rows(2) + gauge.cm_for_rows(cap_rows)
        cuff_sts = sleeve_upper_sts
        sleeve_incs = 0
    sleeve_body_cm = sleeve_length_cm - cuff_cm - cap_cm
    sleeve_body_rows = 2 if style is SleeveStyle.CAP else gauge.rows_for_cm(max(0.0, sleeve_body_cm))
    if sleeves and sleeve_body_rows < 2:
        raise fail()
    puff_sts = 0
    if style is SleeveStyle.BELL:
        bell = bell_width(sleeve_upper_sts, 2)
        bell = min(bell, sleeve_upper_sts + 2 * (sleeve_body_rows // 2 - 1))
        if bell > sleeve_upper_sts:
            cuff_sts = bell
            sleeve_incs = -((bell - sleeve_upper_sts) // 2)
        else:
            style = SleeveStyle.STRAIGHT
    elif style is SleeveStyle.PUFF:
        puff_sts = puff_width(sleeve_upper_sts)
        ups = _puff_rows(cuff_sts, puff_sts)
        downs = len(gather_rounds(puff_sts, sleeve_upper_sts))
        if 2 * (ups + downs) + 2 > sleeve_body_rows:
            style = SleeveStyle.STRAIGHT
            puff_sts = 0
        else:
            sleeve_incs = 0
    # Copa: 2 hileras de cierre de sisa + disminuciones (LD) + 4 hileras de
    # cierre de 2 pts; arriba quedan entre 5 y 8 cm.
    top_target = _even(6.5 * gauge.stitches_per_cm)
    after_bo = sleeve_upper_sts - 2 * armhole_bo - 8
    middle_rows = cap_rows - 2 - 4
    cap_decs = max(0, min((after_bo - top_target) // 2, middle_rows // 2))
    cap_top = after_bo - 2 * cap_decs
    if cap_top < 2:
        raise fail()
    if style is SleeveStyle.STRAIGHT and 2 * sleeve_incs > sleeve_body_rows:
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
        neck_depth_rows=neck_depth_rows,
        neck_decs=neck_decs,
        neck_center_bo=neck_center - 2 * neck_decs,
        neck_sts=neckband_sts,
        neckband_rows=max(1, gauge.rows_for_cm(neckband_cm(spec, NECKBAND_CM))),
        body_length_cm=body_length_cm,
        sleeve_length_cm=sleeve_length_cm,
        armhole_cm=armhole_cm,
        ease=ease,
        hem_sts=hem_sts,
        sleeves=sleeves,
        armhole_band_sts=_armhole_band_sts(armhole_bo, armhole_decs, armhole_rows),
        armhole_band_rows=max(2, gauge.rows_for_cm(ARMHOLE_BAND_CM)),
        neckband_cm=neckband_cm(spec, NECKBAND_CM),
        placket=placket,
        sleeve_style=style,
        puff_sts=puff_sts,
        cuff_cm=cuff_cm,
    )
    return plan, gauge, size


def _armhole_band_sts(bind_off: int, decs: int, rows: int) -> int:
    """Pts de la tira de una sisa (espalda + delantero): 1 por pt cerrado o
    disminuido y 3 de cada 4 hileras rectas. ASUNCION, como la tira del cuello."""
    total = 2 * (bind_off + decs + round_half_up(0.75 * (rows - 2 - 2 * decs)))
    return total + total % 2


def _puff_rows(start: int, wide: int) -> int:
    """Hileras de aumento (cada una suma como mucho los pts que hay)."""
    count = 0
    while start < wide:
        start += min(wide - start, start)
        count += 1
    return count


def _body_panel(
    section_id: str,
    name_key: str,
    plan: SetInPlan,
    spec: GarmentSpec,
    params: PatternParams,
    *,
    neck: bool = False,
) -> tuple[Section, ...]:
    width = max(plan.hem_sts, plan.body_sts)
    rib = get_stitch("rib_2x2" if width % 4 == 0 else "rib_1x1")
    rows = _Rows(0)
    rows.add((Op(StitchKind.CAST_ON, times=width),), "pattern.note.cast_on_panel")
    for index in range(plan.hem_rows):
        rows.add(expand_row(rib, width, index + 1), "pattern.note.hem" if index == 0 else None)
    motif = texture_motif(spec)
    # El panel tiene que entrar en el ancho de espalda (lo mas angosto).
    panel = build_panel(motif, plan.cross_sts) if motif else None
    panel_start = len(rows.steps)
    if panel is not None:
        extra = compensation(panel, resolve_gauge(params).stitches_per_cm, params.panel_motivo_cm)
        rows.start_panel(panel, extra if plan.underarm_rows > 6 else 0)
    flare = (width - plan.body_sts) // 2
    first = plan.hem_rows + 4  # numero de hilera (la 1 es el montaje)
    candidates = [n for n in range(first, plan.hem_rows + plan.underarm_rows - 3) if n % 2 == 1]
    at = {candidates[i - 1] for i in regular_rows(len(candidates), flare)} if flare else set()
    for index in range(plan.underarm_rows):
        if rows.number in at:
            rows.decrease_edges("garments.note.skirt_decrease" if rows.number == min(at) else None)
            continue
        rows.plain("pattern.note.flat_panel" if index == 0 and panel is None else None)
    armhole_start = len(rows.steps)
    if plan.armhole_bo:
        if not rows.right_side:
            rows.plain()
        rows.bind_off_start(plan.armhole_bo, "pattern.note.armhole_shaping")
        rows.bind_off_start(plan.armhole_bo)
    for _ in range(plan.armhole_decs):
        rows.decrease_edges("pattern.note.armhole_decrease")
        rows.plain()
    target = plan.armhole_rows - (plan.neck_depth_rows if neck else 0)
    if neck and plan.placket is not None:
        target -= plan.placket.rows + 1
    while len(rows.steps) - armhole_start < target:
        if rows.extra and target - (len(rows.steps) - armhole_start) <= 2:
            rows.remove_compensation()
            continue
        rows.plain()
    if rows.current != plan.cross_sts:
        raise RuntimeError(f"{section_id}: termina con {rows.current}, se esperaban {plan.cross_sts}")
    shoulder = (plan.cross_sts - plan.neck_center) // 2
    if neck:
        sides: tuple[Section, Section]
        if plan.placket is not None:
            before, after = rows.split_for_neck(plan.placket.width, "garments.note.placket_split")
            side_rows = plan.armhole_rows - (len(rows.steps) - armhole_start)
            sides = placket_sides(
                before,
                after,
                plan.placket,
                side_rows,
                plan.neck_depth_rows,
                (plan.neck_center_bo - plan.placket.width) // 2,
                plan.neck_decs,
            )
        else:
            before, after = rows.split_for_neck(plan.neck_center_bo, "pattern.note.neck_split")
            side_rows = plan.armhole_rows - (len(rows.steps) - armhole_start)
            sides = neck_sections(before, after, plan.neck_decs, side_rows, shoulder)
        front = Section(
            id=section_id,
            name_key=name_key,
            mode="flat",
            steps=tuple(rows.steps),
            start_stitches=0,
            end_stitches=rows.current,
            target=SectionTarget(
                measurement_key=f"{section_id}_length",
                target_cm=plan.body_length_cm * (len(rows.steps) - 1) / plan.body_rows,
                tolerance_cm=1.0,
                dimension="length",
            ),
            meta={
                "row_count": len(rows.steps) - 1,
                "cast_on": width,
                "armhole_bo": plan.armhole_bo,
                **rows.panel_meta(panel_start, plan.cross_sts),
            },
        )
        return (front, *sides)
    return (Section(
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
            "cast_on": width,
            "armhole_bo": plan.armhole_bo,
            "shoulder": shoulder,
            "neck_center": plan.neck_center,
            **rows.panel_meta(panel_start, plan.cross_sts),
        },
        bind_off=True,
    ),)


def _cuff(side: str, plan: SetInPlan) -> Section:
    rib = get_stitch(
        "garter"
        if plan.sleeve_style is SleeveStyle.BELL
        else "rib_2x2" if plan.cuff_sts % 4 == 0 else "rib_1x1"
    )
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
            target_cm=plan.cuff_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": plan.cuff_rows, "cast_on": plan.cuff_sts},
    )


def _sleeve(side: str, plan: SetInPlan) -> Section:
    """Manga desde el puno: aumentos en los bordes en hileras del LD y copa."""
    rows = _Rows(plan.cuff_sts)
    half = plan.sleeve_body_rows // 2
    changes = abs(plan.sleeve_incs)
    increase_at = {2 * r - 1 for r in regular_rows(half, changes)} if changes else set()
    if plan.sleeve_style is SleeveStyle.PUFF:
        _puff_sleeve_body(rows, plan)
    for index in range(plan.sleeve_body_rows if plan.sleeve_style is not SleeveStyle.PUFF else 0):
        note = "pattern.note.flat_panel" if index == 0 else None
        if index + 1 in increase_at and plan.sleeve_incs < 0:
            rows.decrease_edges("garments.note.bell_decrease")
        elif index + 1 in increase_at:
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
            target_cm=plan.sleeve_length_cm - plan.cuff_cm,
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


def _puff_sleeve_body(rows: _Rows, plan: SetInPlan) -> None:
    """Manga globo de abajo hacia arriba: aumentos repartidos despues del
    puno, tramo recto y frunce (disminuciones repartidas) antes de la copa."""
    first = True
    while rows.current < plan.puff_sts:
        count = min(plan.puff_sts - rows.current, rows.current)
        rows.add(spread_increases(rows.current, count), "garments.note.puff_increase" if first else None)
        rows.plain()
        first = False
    gathers = gather_rounds(plan.puff_sts, plan.sleeve_upper_sts)
    while len(rows.steps) < plan.sleeve_body_rows - 2 * len(gathers):
        rows.plain()
    for index, count in enumerate(gathers):
        rows.add(spread_decreases(rows.current, count), "garments.note.puff_gather" if index == 0 else None)
        rows.plain()


def _armhole_band(side: str, plan: SetInPlan) -> Section:
    rib = get_stitch("rib_1x1")
    sts = plan.armhole_band_sts
    steps: list[Step] = [build_step(1, 0, (Op(StitchKind.CAST_ON, times=sts),), note_key="pattern.note.cast_on_panel")]
    for number in range(2, plan.armhole_band_rows + 2):
        steps.append(
            build_step(
                number,
                sts,
                expand_row(rib, sts, number - 1),
                note_key="garments.note.armhole_band" if number == 2 else None,
            )
        )
    return Section(
        id=f"armhole_band_{side}",
        name_key=f"garments.section.armhole_band_{side}",
        mode="flat",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=sts,
        meta={"row_count": plan.armhole_band_rows, "cast_on": sts},
        bind_off=True,
    )


def _neckband(plan: SetInPlan, spec: GarmentSpec) -> Section:
    rib = get_stitch("rib_1x1")
    polo = spec.escote is Neckline.POLO and plan.placket is not None
    polo_note = "garments.note.polo_collar"
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
                note_key=(polo_note if polo else "pattern.note.neckband_sew") if number == 2 else None,
            )
        )
    return Section(
        id="neck_band",
        name_key="garments.section.collar" if polo else "section.neckband",
        mode="flat",
        steps=tuple(steps),
        start_stitches=0,
        end_stitches=plan.neck_sts,
        target=SectionTarget(
            measurement_key="neckband_length",
            target_cm=plan.neckband_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": plan.neckband_rows, "cast_on": plan.neck_sts},
        bind_off=True,
    )


def _warnings(
    spec: GarmentSpec, params: PatternParams, base_id: str, plan: SetInPlan
) -> tuple[Warning, ...]:
    warnings: list[Warning] = [
        Warning("gauge_sample", "warning.gauge_sample", severity="info"),
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", "warning.assumption", severity="info"),
        Warning("flat_panels", "warning.flat_panels"),
    ]
    if plan.sleeves and sleeve_style(spec) is not plan.sleeve_style:
        warnings.append(Warning("sleeve_style_straight", "garments.warning.sleeve_style_straight"))
    if spec.escote in {Neckline.HENLEY, Neckline.POLO} and plan.placket is None:
        warnings.append(Warning("no_placket", "garments.warning.no_placket"))
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
    plan: SetInPlan, gauge: Gauge, size: BodySize, spec: GarmentSpec
) -> tuple[Measurement, ...]:
    # El escote no puede pasar el ancho de espalda: el objetivo es el que entra.
    neck_target = min(neck_cm(spec, size), gauge.cm_for_stitches(2 * plan.neck_center) + 2.0)
    tol = MEASUREMENT_TOLERANCE_CM
    sleeve: tuple[Measurement, ...] = ()
    if plan.sleeves:
        sleeve = (
            Measurement(
                "sleeve_length",
                gauge.cm_for_rows(plan.cuff_rows + plan.sleeve_body_rows + plan.cap_rows),
                plan.sleeve_length_cm,
                2.0,
                "length",
            ),
            Measurement(
                "upper_arm",
                gauge.cm_for_stitches(plan.sleeve_upper_sts),
                size.upper_arm_cm + SLEEVE_EASE_CM,
                tol,
                "circumference",
            ),
        )
    hem: tuple[Measurement, ...] = ()
    if spec.categoria is Category.DRESS or spec.forma is Shape.A_LINE:
        hem = (Measurement("hem", gauge.cm_for_stitches(2 * plan.hem_sts), None, tol, "circumference"),)
    return (
        Measurement("bust", gauge.cm_for_stitches(2 * plan.body_sts), size.bust_cm + plan.ease, tol, "circumference"),
        Measurement("body_length", gauge.cm_for_rows(plan.body_rows), plan.body_length_cm, 1.5, "length"),
        *sleeve,
        Measurement(
            "cross_back",
            gauge.cm_for_stitches(plan.cross_sts),
            min(size.cross_back_cm, gauge.cm_for_stitches(plan.body_sts - 4)),
            tol,
            "width",
        ),
        Measurement("armhole", gauge.cm_for_rows(plan.armhole_rows), plan.armhole_cm, 1.5, "length"),
        Measurement("neck", gauge.cm_for_stitches(2 * plan.neck_center), neck_target, tol, "circumference"),
        *hem,
    )


def generate_set_in(spec: GarmentSpec, params: PatternParams) -> Pattern:
    plan, gauge, size = plan_set_in(spec, params)
    base_id = catalog_id_for_name(spec.punto_base or StitchPatternName.STOCKINETTE)
    if base_id == "other":
        base_id = "stockinette"
    pieces: list[Section] = [
        *_body_panel("back", "section.back", plan, spec, params),
        *_body_panel("front", "section.front", plan, spec, params, neck=True),
    ]
    if plan.placket is not None:
        pieces += [
            placket_band(side, plan.placket.width, plan.placket.rows, buttonholes=side == "right")
            for side in ("right", "left")
        ]
    if plan.sleeves:
        pieces += [_cuff("left", plan), _sleeve("left", plan), _cuff("right", plan), _sleeve("right", plan)]
    else:
        pieces += [_armhole_band("left", plan), _armhole_band("right", plan)]
    pieces.append(_neckband(plan, spec))
    sections = tuple(pieces)
    body_area = (
        2
        * gauge.cm_for_stitches(plan.body_sts)
        * gauge.cm_for_rows(plan.body_rows)
    )
    sleeve_area = (
        2
        * gauge.cm_for_stitches(max(plan.sleeve_upper_sts, plan.puff_sts, plan.cuff_sts))
        * gauge.cm_for_rows(plan.sleeve_body_rows + plan.cap_rows)
    ) if plan.sleeves else 2 * gauge.cm_for_stitches(plan.armhole_band_sts) * ARMHOLE_BAND_CM
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
    joins: tuple[JoinCheck, ...] = (
        JoinCheck(
            label_key="join.shoulder_seam",
            left=(CountRef("back", "meta:shoulder"),),
            right=(CountRef("neck_right", "end"),),
        ),
        JoinCheck(
            label_key="join.shoulder_seam",
            left=(CountRef("back", "meta:shoulder"),),
            right=(CountRef("neck_left", "end"),),
        ),
        JoinCheck(
            label_key="join.neck_split",
            left=(CountRef("front", "end"),),
            right=(CountRef("neck_right", "start"), CountRef("neck_left", "start")),
        ),
    )
    if plan.sleeves:
        joins += (
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
        measurements=_measurements(plan, gauge, size, spec),
        materials=materials,
        warnings=_warnings(spec, params, base_id, plan),
        joins=joins,
    )
