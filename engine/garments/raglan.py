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
from engine.distribution import even_positions, paired_decreases
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
    division_ops,
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
    every_round: bool
    neckband_cm: float
    body_length_cm: float
    sleeve_length_cm: float


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
    max_rounds = max(r_body, r_sleeve)
    standard_rows = 1 + 2 * max_rounds
    fast_rows = 1 + max_rounds
    target_yoke_cm = size.armhole_cm + 4.0
    standard_depth_cm = gauge.cm_for_rows(standard_rows)
    fast_depth_cm = gauge.cm_for_rows(fast_rows)
    every_round = standard_depth_cm > target_yoke_cm + 2
    if (
        sleeve_length_cm <= standard_depth_cm + CUFF_CM + 2
        and fast_depth_cm < standard_depth_cm
    ):
        every_round = True
    yoke_rows = fast_rows if every_round else standard_rows
    yoke_depth_cm = gauge.cm_for_rows(yoke_rows)

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
    if cuff_sts >= sleeve_sts:
        cuff_sts = max(4, sleeve_sts - (sleeve_sts % 4))
    sleeve_decreases = (sleeve_sts - cuff_sts) // 2
    capped = False
    if sleeve_decreases > sleeve_rows:
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
    if sleeve_kind is SleeveLength.LONG and gauge.cm_for_stitches(
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
        every_round=every_round,
        neckband_cm=neckband_cm,
        body_length_cm=body_length_cm,
        sleeve_length_cm=sleeve_length_cm,
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

        if not plan.every_round:
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
        note_keys=(
            ("pattern.note.increase_every_round",) if plan.every_round else ()
        ),
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


def _body_section(plan: RaglanPlan, gauge: Gauge) -> Section:
    division = _division(plan)
    first = build_step(
        1, plan.body_before, division_ops(division), note_key="pattern.note.separation"
    )
    steps: list[Step] = [first]
    for number in range(2, plan.body_rows + 1):
        steps.append(
            build_step(
                number,
                plan.body_sts,
                (Op(StitchKind.KNIT, times=plan.body_sts),),
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


def _sleeve_section(side: str, plan: RaglanPlan) -> Section:
    decrease_rows = set(even_positions(plan.sleeve_rows, plan.sleeve_decreases))
    steps: list[Step] = []
    current = plan.sleeve_sts
    for number in range(1, plan.sleeve_rows + 1):
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
            "row_count": plan.sleeve_rows,
            "picked_up": plan.underarm_sts,
            "decreases": plan.sleeve_decreases,
        },
    )


def _cuff_section(side: str, plan: RaglanPlan) -> Section:
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
    if base_id != "stockinette":
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
    if plan.every_round:
        warnings.append(
            Warning(
                "fast_increases",
                "warning.fast_increases",
                params={"cm": round(plan.yoke_depth_cm, 1)},
            )
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
        _body_section(plan, gauge),
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
                if (spec.largo_manga or SleeveLength.LONG)
                in {SleeveLength.SHORT, SleeveLength.THREE_QUARTER}
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
