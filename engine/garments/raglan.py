"""Pullover raglan top-down en redondo.

Construccion:
1. Cuello en elastico 1x1.
2. Canesu con lineas de raglan de 2 puntos. Los aumentos se reparten entre
   cuerpo y mangas (raglan compuesto) para que ambos conteos cierren.
3. Separacion de mangas con puntos montados en la axila.
4. Cuerpo recto hasta el borde inferior en elastico 2x2.
5. Mangas en redondo con disminuciones en la axila y puno en elastico 2x2.

ASUNCIONES documentadas en `DECISIONS.md` y `docs/fuentes.md`: 4 cm de puntos
montados en cada axila, 4 cm de holgura de manga, 4 cm de puno y borde, 3 cm
de cuello. El canesu, el cuerpo y las mangas se generan en jersey; los bordes
en elastico. No se usan hileras cortas.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from engine import ENGINE_VERSION
from engine.distribution import paired_decreases, regular_rows
from engine.garments.base import ImpossibleProportionsError
from engine.garments.options import body_length_cm as _body_length_cm
from engine.garments.options import effective_sleeve, hem_circumference_cm, sleeve_style
from engine.garments.options import neck_cm as _neck_cm
from engine.garments.options import neckband_cm as _neckband_cm
from engine.garments.options import sleeve_length_cm as _sleeve_length_cm
from engine.garments.panels import body_round_with_panels, compensation, panel_for, texture_motif
from engine.garments.shaping import flared_round_body
from engine.garments.sleeves import (
    CAP_BAND_CM,
    bell_round_sleeve,
    bell_width,
    cap_round_sleeve,
    gather_rounds,
    puff_round_sleeve,
    puff_width,
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
    division_ops,
)
from engine.materials import default_needle_mm, estimate_yarn
from engine.rounding import round_half_up
from engine.sizes import BodySize, ease_for_fit, resolve_body_size
from engine.spec import (
    GarmentSpec,
    Neckline,
    PatternParams,
    SleeveLength,
    SleeveStyle,
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
MEASUREMENT_TOLERANCE_CM = 2.5
RAGLAN_STS = 8


@dataclass(frozen=True)
class RaglanPlan:
    neck_sts: int
    back_neck: int
    front_neck: int
    sleeve_neck: int
    underarm_sts: int
    r_body: int
    r_sleeve: int
    body_before: int
    body_sts: int
    sleeve_sts: int
    yoke_rows: int
    yoke_depth_cm: float
    body_underarm_cm: float
    body_rows: int
    hem_rows: int
    sleeve_underarm_cm: float
    sleeve_rows: int
    cuff_sts: int
    cuff_rows: int
    sleeve_decreases: int
    sleeve_capped: bool
    fast_rounds: int
    plain_rounds: int
    neckband_cm: float
    body_length_cm: float
    sleeve_length_cm: float
    hem_sts: int = 0
    sleeve_style: SleeveStyle = SleeveStyle.STRAIGHT
    cuff_cm: float = CUFF_CM


def _split_neck(neck_sts: int) -> tuple[int, int, int]:
    """Reparte el cuello en espalda, delantero y una manga (sin raglan)."""
    total = neck_sts - RAGLAN_STS
    if total < 8:
        raise ImpossibleProportionsError(
            "error.impossible_proportions", yoke=0, body=0, sleeve=0
        )
    back = max(2, round_half_up(total * 0.3))
    front = back
    sleeves_total = total - back - front
    if sleeves_total < 4:
        deficit = 4 - sleeves_total
        back = max(2, back - deficit)
        front = max(2, front - deficit)
        sleeves_total = total - back - front
    sleeve_each = max(2, (sleeves_total // 2) // 2 * 2)
    front += sleeves_total - 2 * sleeve_each
    if front < 2:
        front = 2
        back = total - front - 2 * sleeve_each
    return back, front, sleeve_each


def _choose_counts(
    body_target: float,
    sleeve_target: float,
    body_neck: int,
    sleeve_neck: int,
    underarm_target: int,
) -> tuple[int, int, int]:
    """Elige (axila, aumentos cuerpo, aumentos manga) que mejor cierran."""
    best_key: tuple[float, int, int, int] | None = None
    best: tuple[int, int, int] | None = None
    for underarm in range(max(2, underarm_target - 10), underarm_target + 11, 2):
        body_est = round_half_up(
            (body_target - body_neck - RAGLAN_STS - 2 * underarm) / 4
        )
        sleeve_est = round_half_up((sleeve_target - sleeve_neck - underarm) / 2)
        for r_body in range(max(0, body_est - 6), max(0, body_est + 6) + 1):
            body_final = body_neck + RAGLAN_STS + 4 * r_body + 2 * underarm
            if body_final <= 0 or body_final % 4 != 0:
                continue
            for r_sleeve in range(max(0, sleeve_est - 6), max(0, sleeve_est + 6) + 1):
                sleeve_final = sleeve_neck + 2 * r_sleeve + underarm
                if sleeve_final <= 0 or sleeve_final % 2 != 0:
                    continue
                score = (
                    abs(body_final - body_target)
                    + abs(sleeve_final - sleeve_target)
                    + 0.05 * abs(underarm - underarm_target)
                )
                key = (score, underarm, r_body, r_sleeve)
                if best_key is None or key < best_key:
                    best_key = key
                    best = (underarm, r_body, r_sleeve)
    if best is None:
        raise ImpossibleProportionsError(
            "error.impossible_proportions", yoke=0, body=body_target, sleeve=sleeve_target
        )
    return best


def plan_raglan(
    spec: GarmentSpec, params: PatternParams
) -> tuple[RaglanPlan, Gauge, BodySize, float]:
    size = resolve_body_size(params.talla, params.medidas_cm)
    gauge = resolve_gauge(params)
    ease = params.ease_cm if params.ease_cm is not None else ease_for_fit(spec.ajuste)
    body_length_cm = _body_length_cm(spec, size)
    sleeve_length_cm = _sleeve_length_cm(spec, size)
    neck_cm = _neck_cm(spec, size)
    neckband_cm = _neckband_cm(spec)
    bust_cm = size.bust_cm + ease
    body_target = max(8.0, bust_cm * gauge.stitches_per_cm)
    neck_sts = max(
        16, round_half_up(neck_cm * gauge.stitches_per_cm / 4.0) * 4
    )
    back_neck, front_neck, sleeve_neck = _split_neck(neck_sts)
    sleeve_target = max(
        4.0, (size.upper_arm_cm + SLEEVE_EASE_CM) * gauge.stitches_per_cm
    )
    underarm_target = gauge.stitches_for_cm(UNDERARM_CM)
    underarm_target = max(2, underarm_target + (underarm_target % 2))
    underarm, r_body, r_sleeve = _choose_counts(
        body_target,
        sleeve_target,
        back_neck + front_neck,
        sleeve_neck,
        underarm_target,
    )

    body_before = back_neck + front_neck + RAGLAN_STS + 4 * r_body
    body_sts = body_before + 2 * underarm
    sleeve_sts = sleeve_neck + 2 * r_sleeve + underarm
    # Esquema estandar de raglan: F vueltas de aumento seguidas, S vueltas de
    # aumento cada 2 vueltas y P vueltas sin aumentos, para que la
    # profundidad del canesu llegue al objetivo en todos los talles. Antes se
    # pasaba a "aumentar en todas las vueltas" y la sisa caia a la mitad.
    max_rounds = max(r_body, r_sleeve)
    target_yoke_cm = size.armhole_cm + 4.0
    style = sleeve_style(spec)
    sleeve_room = sleeve_length_cm - CUFF_CM if style is not SleeveStyle.CAP else body_length_cm
    room_cm = min(body_length_cm - HEM_CM, sleeve_room) - 2.5
    target_rows = gauge.rows_for_cm(min(target_yoke_cm, room_cm))
    yoke_rows = max(1 + max_rounds, target_rows)
    fast_rounds = min(max_rounds, max(0, 1 + 2 * max_rounds - yoke_rows))
    plain_rounds = yoke_rows - (1 + fast_rounds + 2 * (max_rounds - fast_rounds))
    yoke_depth_cm = gauge.cm_for_rows(yoke_rows)

    if body_length_cm <= yoke_depth_cm + HEM_CM + 2:
        raise ImpossibleProportionsError(
            "error.impossible_proportions",
            yoke=round(yoke_depth_cm, 1),
            body=body_length_cm,
            sleeve=sleeve_length_cm,
        )
    sleeve_kind = effective_sleeve(spec)
    cuff_cm = CUFF_CM
    if style is SleeveStyle.CAP:
        # Casquillo: la manga es solo la tira, apenas debajo de la axila.
        cuff_cm = CAP_BAND_CM
        sleeve_length_cm = yoke_depth_cm + gauge.cm_for_rows(1 if sleeve_sts % 4 == 0 else 2) + cuff_cm
    elif sleeve_kind is not SleeveLength.LONG and sleeve_length_cm <= yoke_depth_cm + CUFF_CM + 2:
        # Manga corta en un canesu muy hondo (talles grandes, hilo fino):
        # ASUNCION: la manga llega al menos 2,5 cm debajo de la axila.
        sleeve_length_cm = yoke_depth_cm + CUFF_CM + 2.5
    if sleeve_length_cm <= yoke_depth_cm + cuff_cm + 2 and style is not SleeveStyle.CAP:
        raise ImpossibleProportionsError(
            "error.impossible_proportions",
            yoke=round(yoke_depth_cm, 1),
            body=body_length_cm,
            sleeve=sleeve_length_cm,
        )

    body_underarm_cm = body_length_cm - yoke_depth_cm - HEM_CM
    body_rows = max(1, gauge.rows_for_cm(body_underarm_cm))
    hem_rows = max(1, gauge.rows_for_cm(HEM_CM))
    hem_target = hem_circumference_cm(spec, size, ease) * gauge.stitches_per_cm
    flare = max(0, round_half_up((hem_target - body_sts) / 4))
    flare = min(flare, max(0, body_rows - 2))
    if texture_motif(spec) is not None:
        flare = 0  # con panel de textura el cuerpo va recto (aviso)
    hem_sts = body_sts + 4 * flare

    sleeve_underarm_cm = sleeve_length_cm - yoke_depth_cm - cuff_cm
    sleeve_rows = max(1, gauge.rows_for_cm(sleeve_underarm_cm))
    cuff_rows = max(1, gauge.rows_for_cm(cuff_cm))
    if style is SleeveStyle.CAP:
        sleeve_rows = 1 if sleeve_sts % 4 == 0 else 2
        sleeve_underarm_cm = gauge.cm_for_rows(sleeve_rows)

    cuff_target_cm = size.wrist_cm + CUFF_EASE_CM
    if sleeve_kind is SleeveLength.THREE_QUARTER:
        cuff_target_cm += 2.0
    if sleeve_kind is SleeveLength.ELBOW:
        # ASUNCION: a la altura del codo, el promedio entre muneca y brazo.
        cuff_target_cm = (size.wrist_cm + size.upper_arm_cm) / 2 + CUFF_EASE_CM
    if style is SleeveStyle.PUFF and sleeve_kind in {SleeveLength.SHORT, SleeveLength.ELBOW}:
        cuff_target_cm = size.upper_arm_cm + CUFF_EASE_CM  # tira que ajusta el brazo
    cuff_sts = max(
        4, round_half_up(cuff_target_cm * gauge.stitches_per_cm / 4.0) * 4
    )
    if cuff_sts >= sleeve_sts:
        cuff_sts = max(4, sleeve_sts - (sleeve_sts % 4))
    if style is SleeveStyle.CAP:
        cuff_sts = sleeve_sts - sleeve_sts % 4
    elif style is SleeveStyle.BELL:
        cuff_sts = min(bell_width(sleeve_sts), sleeve_sts + 2 * (sleeve_rows - 1))
        cuff_sts -= (cuff_sts - sleeve_sts) % 2
        while cuff_sts % 4:
            cuff_sts -= 2
        if cuff_sts <= sleeve_sts:
            style = SleeveStyle.STRAIGHT  # no hay largo para abrir la campana
            cuff_sts = max(4, sleeve_sts - (sleeve_sts % 4))
    elif style is SleeveStyle.PUFF and sleeve_rows < 3 + len(gather_rounds(puff_width(sleeve_sts), cuff_sts)):
        style = SleeveStyle.STRAIGHT
    sleeve_decreases = (sleeve_sts - cuff_sts) // 2
    capped = False
    if style is not SleeveStyle.STRAIGHT:
        sleeve_decreases = 0
    elif sleeve_decreases > sleeve_rows:
        capped = True
        sleeve_decreases = sleeve_rows
        raw_cuff = sleeve_sts - 2 * sleeve_decreases
        cuff_sts = adjust_stitches(max(4, raw_cuff), 4, mode="up")
        if cuff_sts > sleeve_sts:
            cuff_sts = max(4, sleeve_sts - (sleeve_sts % 4))
        sleeve_decreases = (sleeve_sts - cuff_sts) // 2
    if sleeve_decreases > sleeve_rows:
        raise ImpossibleProportionsError(
            "error.impossible_proportions",
            yoke=round(yoke_depth_cm, 1),
            body=body_length_cm,
            sleeve=sleeve_length_cm,
        )
    if sleeve_kind is SleeveLength.LONG and style is SleeveStyle.STRAIGHT and gauge.cm_for_stitches(
        cuff_sts
    ) > size.wrist_cm + CUFF_EASE_CM + MEASUREMENT_TOLERANCE_CM:
        raise ImpossibleProportionsError(
            "error.impossible_proportions",
            yoke=round(yoke_depth_cm, 1),
            body=body_length_cm,
            sleeve=sleeve_length_cm,
        )

    plan = RaglanPlan(
        neck_sts=neck_sts,
        back_neck=back_neck,
        front_neck=front_neck,
        sleeve_neck=sleeve_neck,
        underarm_sts=underarm,
        r_body=r_body,
        r_sleeve=r_sleeve,
        body_before=body_before,
        body_sts=body_sts,
        sleeve_sts=sleeve_sts,
        yoke_rows=yoke_rows,
        yoke_depth_cm=yoke_depth_cm,
        body_underarm_cm=body_underarm_cm,
        body_rows=body_rows,
        hem_rows=hem_rows,
        sleeve_underarm_cm=sleeve_underarm_cm,
        sleeve_rows=sleeve_rows,
        cuff_sts=cuff_sts,
        cuff_rows=cuff_rows,
        sleeve_decreases=sleeve_decreases,
        sleeve_capped=capped,
        fast_rounds=fast_rounds,
        plain_rounds=plain_rounds,
        neckband_cm=neckband_cm,
        body_length_cm=body_length_cm,
        sleeve_length_cm=sleeve_length_cm,
        hem_sts=hem_sts,
        sleeve_style=style,
        cuff_cm=cuff_cm,
    )
    return plan, gauge, size, ease


def _neckband_section(plan: RaglanPlan, gauge: Gauge) -> Section:
    rib = get_stitch("rib_1x1")
    rows = max(1, gauge.rows_for_cm(plan.neckband_cm))
    steps = tuple(
        build_step(
            number,
            plan.neck_sts,
            expand_row(rib, plan.neck_sts, number, in_the_round=True),
            note_key="pattern.note.neckband" if number == 1 else None,
        )
        for number in range(1, rows + 1)
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
        meta={"row_count": rows},
    )


def _yoke_section(plan: RaglanPlan) -> Section:
    steps: list[Step] = [
        build_step(
            1,
            plan.neck_sts,
            (Op(StitchKind.KNIT, times=plan.neck_sts),),
            note_key="pattern.note.yoke_setup",
        )
    ]
    back = plan.back_neck
    front = plan.front_neck
    sleeve = plan.sleeve_neck
    number = 1
    max_rounds = max(plan.r_body, plan.r_sleeve)
    for index in range(1, max_rounds + 1):
        body_inc = index <= plan.r_body
        sleeve_inc = index <= plan.r_sleeve
        items: list[Op] = []
        if body_inc:
            items.append(Op(StitchKind.M1L))
        if back:
            items.append(Op(StitchKind.KNIT, times=back))
        if body_inc:
            items.append(Op(StitchKind.M1R))
        items.append(Op(StitchKind.KNIT, times=2))
        if sleeve_inc:
            items.append(Op(StitchKind.M1L))
        if sleeve:
            items.append(Op(StitchKind.KNIT, times=sleeve))
        if sleeve_inc:
            items.append(Op(StitchKind.M1R))
        items.append(Op(StitchKind.KNIT, times=2))
        if body_inc:
            items.append(Op(StitchKind.M1L))
        if front:
            items.append(Op(StitchKind.KNIT, times=front))
        if body_inc:
            items.append(Op(StitchKind.M1R))
        items.append(Op(StitchKind.KNIT, times=2))
        if sleeve_inc:
            items.append(Op(StitchKind.M1L))
        if sleeve:
            items.append(Op(StitchKind.KNIT, times=sleeve))
        if sleeve_inc:
            items.append(Op(StitchKind.M1R))
        items.append(Op(StitchKind.KNIT, times=2))

        if body_inc and sleeve_inc:
            note = "pattern.note.increase_both"
        elif body_inc:
            note = "pattern.note.increase_body"
        else:
            note = "pattern.note.increase_sleeve"
        number += 1
        total = back + front + 2 * sleeve + RAGLAN_STS
        steps.append(build_step(number, total, items, note_key=note))
        if body_inc:
            back += 2
            front += 2
        if sleeve_inc:
            sleeve += 2

        if index > plan.fast_rounds:
            number += 1
            total = back + front + 2 * sleeve + RAGLAN_STS
            steps.append(
                build_step(
                    number,
                    total,
                    (Op(StitchKind.KNIT, times=total),),
                    note_key="pattern.note.plain",
                )
            )

    end = plan.neck_sts + 4 * plan.r_body + 4 * plan.r_sleeve
    for _ in range(plan.plain_rounds):
        number += 1
        steps.append(
            build_step(number, end, (Op(StitchKind.KNIT, times=end),), note_key="pattern.note.plain")
        )
    return Section(
        id="yoke",
        name_key="section.yoke",
        mode="round",
        steps=tuple(steps),
        start_stitches=plan.neck_sts,
        end_stitches=end,
        target=SectionTarget(
            measurement_key="yoke_depth",
            target_cm=plan.yoke_depth_cm,
            tolerance_cm=0.1,
            dimension="length",
        ),
        meta={
            "row_count": plan.yoke_rows,
            "expected_increases": 4 * plan.r_body + 4 * plan.r_sleeve,
            "expected_decreases": 0,
            "back_neck": plan.back_neck,
            "front_neck": plan.front_neck,
            "sleeve_neck": plan.sleeve_neck,
            "back_final": plan.back_neck + 2 * plan.r_body,
            "front_final": plan.front_neck + 2 * plan.r_body,
            "sleeve_final": plan.sleeve_neck + 2 * plan.r_sleeve,
            "underarm": plan.underarm_sts,
            "body_before": plan.body_before,
            "body": plan.body_sts,
        },
    )


def _division(plan: RaglanPlan) -> tuple[tuple[str, int], ...]:
    """Vuelta de separacion en orden fisico.

    Al final del canesu la vuelta es: espalda, raglan, manga, raglan,
    delantero, raglan, manga, raglan. Los puntos de raglan quedan en el cuerpo.
    """
    line = RAGLAN_STS // 4
    back = plan.back_neck + 2 * plan.r_body
    front = plan.front_neck + 2 * plan.r_body
    sleeve = plan.sleeve_neck + 2 * plan.r_sleeve
    return (
        ("knit", back + line),
        ("hold", sleeve),
        ("cast_on", plan.underarm_sts),
        ("knit", line + front + line),
        ("hold", sleeve),
        ("cast_on", plan.underarm_sts),
        ("knit", line),
    )


def _body_section(plan: RaglanPlan, gauge: Gauge, spec: GarmentSpec, params: PatternParams) -> Section:
    division = _division(plan)
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
    if plan.hem_sts > plan.body_sts:
        steps = flared_round_body(division, plan.body_before, plan.body_sts, plan.body_rows, plan.hem_sts)
    for number in range(2 if len(steps) == 1 else plan.body_rows + 1, plan.body_rows + 1):
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
        end_stitches=steps[-1].stitch_count_end,
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


def _hem_section(plan: RaglanPlan, gauge: Gauge) -> Section:
    rib = get_stitch("rib_2x2")
    hem = max(plan.hem_sts, plan.body_sts)
    steps = tuple(
        build_step(
            number,
            hem,
            expand_row(rib, hem, number, in_the_round=True),
            note_key="pattern.note.hem" if number == 1 else None,
        )
        for number in range(1, plan.hem_rows + 1)
    )
    return Section(
        id="hem",
        name_key="section.hem",
        mode="round",
        steps=steps,
        start_stitches=hem,
        end_stitches=hem,
        target=SectionTarget(
            measurement_key="hem_length",
            target_cm=HEM_CM,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": plan.hem_rows},
        bind_off=True,
    )


def _sleeve_section(side: str, plan: RaglanPlan) -> Section:
    decrease_rows = set(regular_rows(plan.sleeve_rows, plan.sleeve_decreases))
    steps: list[Step] = []
    current = plan.sleeve_sts
    rows = plan.sleeve_rows
    if plan.sleeve_style is SleeveStyle.PUFF:
        steps = puff_round_sleeve(current, rows, plan.cuff_sts)
    elif plan.sleeve_style is SleeveStyle.BELL:
        steps = bell_round_sleeve(current, rows, plan.cuff_sts)
    elif plan.sleeve_style is SleeveStyle.CAP:
        steps, _ = cap_round_sleeve(current)
        rows = len(steps)
    if steps:
        current = steps[-1].stitch_count_end
    for number in range(1 if not steps else rows + 1, rows + 1):
        if number in decrease_rows:
            ops, new_count = paired_decreases(current, 1, 1)
            steps.append(
                build_step(
                    number, current, ops, note_key="pattern.note.decrease_sleeve"
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
            "row_count": len(steps),
            "picked_up": plan.underarm_sts,
            "decreases": plan.sleeve_decreases,
        },
    )


def _cuff_section(side: str, plan: RaglanPlan) -> Section:
    rib = get_stitch("garter" if plan.sleeve_style is SleeveStyle.BELL else "rib_2x2")
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
            target_cm=plan.cuff_cm,
            tolerance_cm=0.5,
            dimension="length",
        ),
        meta={"row_count": plan.cuff_rows},
        bind_off=True,
    )


def _warnings(
    spec: GarmentSpec,
    params: PatternParams,
    plan: RaglanPlan,
    ease: float,
    base_id: str,
) -> tuple[Warning, ...]:
    warnings: list[Warning] = [
        Warning("gauge_sample", "warning.gauge_sample", severity="info"),
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", "warning.assumption", severity="info"),
    ]
    if spec.escote not in {None, Neckline.NONE}:
        warnings.append(Warning("no_short_rows", "warning.no_short_rows"))
    if ease < 0:
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
    if plan.yoke_depth_cm > 35:
        warnings.append(
            Warning(
                "yoke_depth",
                "warning.yoke_depth",
                params={"cm": round(plan.yoke_depth_cm, 1)},
            )
        )
    if plan.sleeve_capped:
        warnings.append(
            Warning("sleeve_decrease_limit", "warning.sleeve_decrease_limit")
        )
    if spec.escote is Neckline.HOOD:
        warnings.append(
            Warning(
                "unsupported_variant",
                "warning.unsupported_variant",
                params={"variant": "hood"},
            )
        )
    return tuple(warnings)


def generate_raglan_top_down(
    spec: GarmentSpec, params: PatternParams
) -> Pattern:
    plan, gauge, size, ease = plan_raglan(spec, params)
    base_id = catalog_id_for_name(
        spec.punto_base or StitchPatternName.STOCKINETTE
    )
    if base_id == "other":
        base_id = "stockinette"

    sections = (
        _neckband_section(plan, gauge),
        _yoke_section(plan),
        _body_section(plan, gauge, spec, params),
        _hem_section(plan, gauge),
        _sleeve_section("left", plan),
        _cuff_section("left", plan),
        _sleeve_section("right", plan),
        _cuff_section("right", plan),
    )

    body_length_cm = (
        plan.yoke_depth_cm
        + gauge.cm_for_rows(plan.body_rows)
        + gauge.cm_for_rows(plan.hem_rows)
    )
    sleeve_length_cm = (
        plan.yoke_depth_cm
        + gauge.cm_for_rows(plan.sleeve_rows)
        + gauge.cm_for_rows(plan.cuff_rows)
    )
    measurements = (
        Measurement(
            key="bust",
            value_cm=gauge.cm_for_stitches(plan.body_sts),
            target_cm=size.bust_cm + ease,
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="circumference",
        ),
        Measurement(
            key="body_length",
            value_cm=body_length_cm,
            target_cm=plan.body_length_cm,
            tolerance_cm=1.0,
            kind="length",
        ),
        Measurement(
            key="sleeve_length",
            value_cm=sleeve_length_cm,
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
            target_cm=_neck_cm(spec, size),
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="circumference",
        ),
        Measurement(
            key="wrist",
            value_cm=gauge.cm_for_stitches(plan.cuff_sts),
            target_cm=(
                None
                if effective_sleeve(spec) is not SleeveLength.LONG
                or plan.sleeve_style is not SleeveStyle.STRAIGHT
                else size.wrist_cm + CUFF_EASE_CM
            ),
            tolerance_cm=MEASUREMENT_TOLERANCE_CM,
            kind="circumference",
        ),
        Measurement(
            key="yoke_depth",
            value_cm=plan.yoke_depth_cm,
            target_cm=None,
            kind="length",
        ),
        Measurement(
            key="armhole",
            value_cm=plan.yoke_depth_cm,
            target_cm=None,
            kind="length",
        ),
    )

    body_area = gauge.cm_for_stitches(plan.body_sts) * (
        gauge.cm_for_rows(plan.body_rows) + gauge.cm_for_rows(plan.hem_rows)
    )
    average_sleeve_cm = (
        gauge.cm_for_stitches(plan.sleeve_sts) + gauge.cm_for_stitches(plan.cuff_sts)
    ) / 2
    sleeve_area = 2 * average_sleeve_cm * (
        gauge.cm_for_rows(plan.sleeve_rows) + gauge.cm_for_rows(plan.cuff_rows)
    )
    meters, grams = estimate_yarn(body_area + sleeve_area, params.peso_hilo)
    notions = (
        "notion.stitch_markers",
        "notion.tapestry_needle",
        "notion.waste_yarn",
        "notion.row_counter",
        "notion.tape_measure",
    )
    colors = tuple(spec.colorwork.paleta) if spec.colorwork else ()

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

    digest = hashlib.sha256(
        (spec.model_dump_json() + params.model_dump_json()).encode("utf-8")
    ).hexdigest()[:12]
    meta = PatternMeta(
        id=digest,
        family="raglan_top_down",
        title_key="title.pullover_raglan",
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
        measurements=measurements,
        materials=materials,
        warnings=_warnings(spec, params, plan, ease, base_id),
        joins=joins,
    )
