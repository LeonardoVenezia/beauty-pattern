"""Manos y pies (D038): mitones sin dedos, polainas, escarpines y pantuflas.

- Mitones sin dedos: en redondo. Dos agujas con cuna de pulgar (aumentos en
  pares cada 3 vueltas); crochet con la abertura de pulgar clasica de
  cadenas ("cad n, saltar n").
- Polainas: tubo con elastico arriba y abajo y, si el punto lo permite,
  disminuciones de pantorrilla a tobillo.
- Escarpines (bebe) y pantuflas de crochet: desde la punta, en redondo (la
  suela y el empeine salen de una sola pieza), despues el talon en plano que
  se dobla y se cose, y la cana levantada alrededor del tobillo.
- Pantuflas de dos agujas: la pantufla clasica plana en punto bobo que se
  frunce en la punta y se cose (arriba y en el talon).

Talles con fuente (Craft Yarn Council) o ASUNCION en engine/garments/acc_kit.py.
"""

from __future__ import annotations

import math

from engine.distribution import regular_rows
from engine.garments.acc_kit import (
    ADULT_FOOT,
    BABY_FOOT,
    BABY_SIZES,
    HAND_BY_SIZE,
    LEG_BY_SIZE,
    Craft,
    Row,
    build_section,
    cast_on_row,
    common_warnings,
    craft_for,
    dimension,
    family_name,
    fitted,
    has_finish,
    materials,
    meta,
    nearest_multiple,
    pattern_rows,
    pick_up,
    plain,
    repeat_tolerance,
    tie_section,
    with_gauge,
)
from engine.garments.base import ImpossibleProportionsError
from engine.garments.hats import circle
from engine.gauge import Gauge
from engine.ir import (
    CountRef,
    Item,
    JoinCheck,
    Measurement,
    Note,
    Op,
    Pattern,
    Repeat,
    Section,
    Warning,
)
from engine.rounding import round_half_up
from engine.spec import Finish, GarmentSpec, PatternParams, Shape, resolve_gauge
from engine.stitches.catalog import expand_row, get_stitch
from engine.stitches.kinds import StitchKind


def _tol(gauge: Gauge, base: float = 1.0) -> float:
    return max(base, 1.0 / gauge.rows_per_cm)


def _rib(craft: Craft) -> str | None:
    """Elastico de punos y canas: 1x1 en agujas; en crochet, el punto base
    tejido por la hebra de atras (lo dice la nota)."""
    return None if craft.crochet else "rib_1x1"


def _cuff_note(craft: Craft) -> str:
    return "acc.note.band_crochet" if craft.crochet else "pattern.note.cuff"


# ---------------------------------------------------------------------------
# Mitones sin dedos.
# ---------------------------------------------------------------------------

MITT_EASE = 0.95  # ASUNCION: 5 % menos que la palma (el tejido cede)
MITT_CUFF = 5.0  # ASUNCION: puno de 5 cm
MITT_PALM_SHARE = 0.55  # ASUNCION: de la muneca a los nudillos ~55 % del largo de la mano
THUMB_SHARE = 0.3  # ASUNCION: cuna = 30 % de los pts de la mano
GUSSET_SHARE = 0.38  # ASUNCION: alto de la cuna / largo de la mano


def generate_fingerless_mitts(spec: GarmentSpec, params: PatternParams) -> Pattern:
    craft = craft_for(spec)
    params = with_gauge(craft, params)
    gauge = resolve_gauge(params)
    palm_default, hand_default = HAND_BY_SIZE.get(params.talla.upper(), HAND_BY_SIZE["M"])
    palm = dimension(params, "palm", palm_default)
    hand_length = dimension(params, "hand_length", hand_default)
    multiple = math.lcm(craft.multiple, 2)
    hand = nearest_multiple(palm * MITT_EASE * gauge.stitches_per_cm, multiple, minimum=12)
    cuff_rows = max(2, gauge.rows_for_cm(MITT_CUFF * hand_length / 16.5))
    mitt_cm = dimension(params, "length", hand_length * MITT_PALM_SHARE)
    top_rows = max(1 if craft.crochet else 2, gauge.rows_for_cm(1.5))
    sections: list[Section] = [
        build_section(
            "cuff",
            "section.cuff",
            "round",
            0,
            [
                cast_on_row(craft, hand, round_mode=True),
                *pattern_rows(
                    craft,
                    hand,
                    cuff_rows,
                    round_mode=True,
                    stitch_id=_rib(craft),
                    note=_cuff_note(craft),
                ),
            ],
            gauge,
        )
    ]
    gusset_cm = hand_length * GUSSET_SHARE
    if craft.crochet:
        gap = max(3, round_half_up(hand * THUMB_SHARE / 2))
        above = gauge.rows_for_cm(mitt_cm)
        room = max(2, above - 1 - top_rows)  # vueltas de mano sin la del pulgar
        before = min(max(1, gauge.rows_for_cm(gusset_cm) - 1), room - 1)
        rows = pattern_rows(craft, hand, before, round_mode=True, note="acc.note.mitt_hand")
        rows.append(
            Row(
                (
                    *plain(craft, 1),
                    Op(StitchKind.CH, times=gap),
                    Op(StitchKind.SKIP, times=gap),
                    *plain(craft, hand - gap - 1),
                ),
                "acc.note.thumb_gap",
                (("n", str(gap)),),
            )
        )
        after = room - before
        rows += pattern_rows(craft, hand, after, round_mode=True)
        sections.append(build_section("hand", "section.hand", "round", hand, rows, gauge))
        thumb_start = 2 * gap + 2
        thumb_held = 0
    else:
        thumb = max(4, 2 * round_half_up(hand * THUMB_SHARE / 2))
        stitch = get_stitch(craft.stitch_id)
        gusset_rows: list[Row] = []
        width = 0
        number = 1
        while width < thumb:
            for offset in range(3):
                if offset == 0:
                    lead: tuple[Item, ...] = (
                        Op(StitchKind.M1L),
                        *((Op(StitchKind.KNIT, times=width),) if width else ()),
                        Op(StitchKind.M1R),
                    )
                    note = "acc.note.gusset" if width == 0 else None
                    width_after = width + 2
                else:
                    lead = (Op(StitchKind.KNIT, times=width),)
                    note = None
                    width_after = width
                gusset_rows.append(
                    Row(
                        (*lead, *expand_row(stitch, hand, number, in_the_round=True)),
                        note,
                        (("t", str(thumb)),) if note else (),
                    )
                )
                number += 1
                width = width_after
                if width >= thumb and offset == 0:
                    break
        sections.append(
            build_section("thumb_gusset", "section.thumb_gusset", "round", hand, gusset_rows, gauge)
        )
        after = max(2, gauge.rows_for_cm(mitt_cm) - len(gusset_rows) - top_rows)
        hand_rows = pattern_rows(
            craft,
            hand,
            after,
            round_mode=True,
            first=number,
            note="acc.note.mitt_hold",
            params=(("t", str(thumb)),),
        )
        sections.append(build_section("hand", "section.hand", "round", hand, hand_rows, gauge))
        thumb_start = thumb + 2
        thumb_held = thumb
    top = pattern_rows(
        craft, hand, top_rows, round_mode=True, stitch_id=_rib(craft), note=_cuff_note(craft)
    )
    sections.append(
        build_section("top", "acc.section.mitt_top", "round", hand, top, gauge, bind_off=True)
    )
    thumb_rows = max(2, gauge.rows_for_cm(1.5))
    sections.append(
        build_section(
            "thumb",
            "section.thumb",
            "round",
            thumb_start,
            pattern_rows(
                craft,
                thumb_start,
                thumb_rows,
                round_mode=True,
                stitch_id=_rib(craft),
                note="acc.note.thumb_crochet" if craft.crochet else "acc.note.thumb_pickup",
                params=(("t", str(thumb_held)), ("n", str(thumb_start))),
            ),
            gauge,
            bind_off=True,
            meta={"held": thumb_held},
        )
    )
    joins = [
        JoinCheck(
            "join.cuff",
            (CountRef("cuff", "end"),),
            (CountRef("thumb_gusset" if not craft.crochet else "hand", "start"),),
        )
    ]
    if not craft.crochet:
        joins.append(
            JoinCheck(
                "acc.join.thumb",
                (CountRef("thumb_gusset", "end"),),
                (CountRef("hand", "start"), CountRef("thumb", "meta:held")),
            )
        )
    worked = sum(s.meta["row_count"] for s in sections if s.id != "thumb")
    measurements = [
        Measurement(
            key="palm",
            value_cm=gauge.cm_for_stitches(hand),
            target_cm=palm * MITT_EASE,
            tolerance_cm=repeat_tolerance(gauge, multiple, 1.5),
            kind="circumference",
        ),
        Measurement(
            key="length",
            value_cm=gauge.cm_for_rows(worked),
            target_cm=gauge.cm_for_rows(cuff_rows) + mitt_cm,
            tolerance_cm=_tol(gauge, 1.5),
            kind="length",
        ),
    ]
    return Pattern(
        meta=meta(spec, params, family_name(craft, "fingerless_mitts"), "title.fingerless_mitts"),
        spec=spec,
        params=params,
        sections=tuple(sections),
        measurements=fitted(measurements),
        materials=materials(
            craft,
            spec,
            params,
            2 * gauge.cm_for_stitches(hand) * gauge.cm_for_rows(worked) * 1.15,
            (
                "notion.crochet_hook" if craft.crochet else "notion.stitch_markers",
                "notion.waste_yarn" if not craft.crochet else "notion.stitch_markers",
                "notion.tapestry_needle",
            ),
        ),
        warnings=tuple(common_warnings(craft, params)),
        joins=tuple(joins),
        finishing=(Note("acc.finish.make_pair", {}),),
    )


# ---------------------------------------------------------------------------
# Polainas.
# ---------------------------------------------------------------------------

LEG_ANKLE_EASE = 4.0  # ASUNCION: el tobillo de la polaina queda 4 cm flojo
LEG_LENGTH = 40.0  # ASUNCION: de la rodilla al tobillo
LEG_CUFF = 5.0


def generate_leg_warmers(spec: GarmentSpec, params: PatternParams) -> Pattern:
    craft = craft_for(spec)
    params = with_gauge(craft, params)
    gauge = resolve_gauge(params)
    spc = gauge.stitches_per_cm
    calf_default, ankle_default = LEG_BY_SIZE.get(params.talla.upper(), LEG_BY_SIZE["M"])
    calf = dimension(params, "calf", calf_default)
    ankle = dimension(params, "ankle", ankle_default) + LEG_ANKLE_EASE
    length = dimension(params, "length", LEG_LENGTH)
    multiple = 1 if craft.crochet else math.lcm(craft.multiple, 2)
    top = nearest_multiple(calf * spc, multiple, minimum=16)
    shaped = (
        (craft.crochet or craft.multiple == 1)
        and spec.forma not in {Shape.STRAIGHT, Shape.BOXY}
        and ankle < calf
    )
    # La diferencia tiene que ser par (2 dism por vuelta) y, en agujas, el
    # elastico de abajo necesita un multiplo de 2.
    step = 2 * max(1, multiple // 2) if not craft.crochet else 2
    bottom = top - step * round_half_up((top - ankle * spc) / step) if shaped else top
    if bottom >= top:
        shaped, bottom = False, top
    cuff_rows = max(2, gauge.rows_for_cm(LEG_CUFF))
    leg_rows_total = gauge.rows_for_cm(length) - 2 * cuff_rows
    if leg_rows_total < 4:
        raise ImpossibleProportionsError(
            "acc.error.too_short", cm=f"{length:g}", min=f"{2 * LEG_CUFF + 2:.0f}"
        )
    sections: list[Section] = [
        build_section(
            "cuff_top",
            "acc.section.cuff_top",
            "round",
            0,
            [
                cast_on_row(craft, top, round_mode=True),
                *pattern_rows(
                    craft,
                    top,
                    cuff_rows,
                    round_mode=True,
                    stitch_id=_rib(craft),
                    note=_cuff_note(craft),
                ),
            ],
            gauge,
        )
    ]
    rows: list[Row] = []
    n = top
    decreases = (top - bottom) // 2
    if decreases:
        shaping_rows = max(decreases, leg_rows_total * 2 // 3)
        at = set(regular_rows(shaping_rows, decreases))
        for index in range(1, leg_rows_total + 1):
            if index in at:
                items: tuple[Item, ...] = (
                    *plain(craft, 1),
                    Op(craft.dec),
                    *plain(craft, n - 6),
                    Op(craft.dec_left),
                    *plain(craft, 1),
                )
                rows.append(Row(items, "acc.note.calf_decrease" if index == min(at) else None))
                n -= 2
            else:
                rows.append(
                    Row(
                        pattern_rows(craft, n, 1, round_mode=True, first=index)[0].items,
                        "acc.note.leg" if index == 1 else None,
                    )
                )
    else:
        rows = pattern_rows(craft, n, leg_rows_total, round_mode=True, note="acc.note.leg")
    sections.append(
        build_section(
            "leg",
            "section.leg",
            "round",
            top,
            rows,
            gauge,
            meta={"expected_decreases": 2 * decreases} if decreases else None,
        )
    )
    sections.append(
        build_section(
            "cuff_bottom",
            "acc.section.cuff_bottom",
            "round",
            n,
            pattern_rows(
                craft, n, cuff_rows, round_mode=True, stitch_id=_rib(craft), note=_cuff_note(craft)
            ),
            gauge,
            bind_off=True,
        )
    )
    measurements = [
        Measurement(
            key="calf",
            value_cm=gauge.cm_for_stitches(top),
            target_cm=calf,
            tolerance_cm=repeat_tolerance(gauge, multiple, 2.0),
            kind="circumference",
        ),
        Measurement(
            key="length",
            value_cm=gauge.cm_for_rows(2 * cuff_rows + leg_rows_total),
            target_cm=length,
            tolerance_cm=_tol(gauge, 1.5),
            kind="length",
        ),
    ]
    if shaped:
        measurements.append(
            Measurement(
                key="ankle",
                value_cm=gauge.cm_for_stitches(bottom),
                target_cm=ankle,
                tolerance_cm=repeat_tolerance(gauge, max(3, multiple), 2.0),
                kind="circumference",
            )
        )
    return Pattern(
        meta=meta(spec, params, family_name(craft, "leg_warmers"), "title.leg_warmers"),
        spec=spec,
        params=params,
        sections=tuple(sections),
        measurements=fitted(measurements),
        materials=materials(
            craft,
            spec,
            params,
            2 * (calf + ankle) / 2 * length,
            (
                "notion.crochet_hook" if craft.crochet else "notion.stitch_markers",
                "notion.tapestry_needle",
            ),
        ),
        warnings=tuple(common_warnings(craft, params)),
        joins=(
            JoinCheck(
                "acc.join.leg_top", (CountRef("cuff_top", "end"),), (CountRef("leg", "start"),)
            ),
            JoinCheck(
                "acc.join.leg_bottom",
                (CountRef("leg", "end"),),
                (CountRef("cuff_bottom", "start"),),
            ),
        ),
        finishing=(Note("acc.finish.make_pair", {}),),
    )


# ---------------------------------------------------------------------------
# Escarpines y pantuflas de crochet: desde la punta.
# ---------------------------------------------------------------------------

HEEL_SHARE = 0.4  # ASUNCION: el talon plano ocupa el 40 % del largo del pie
INSTEP_SHARE = 0.4  # ASUNCION: el empeine abierto = 40 % de los pts del pie
BABY_EASE = 1.1  # ASUNCION: escarpin 10 % mas ancho que el pie y 1 cm mas largo


def _toe_up(spec: GarmentSpec, params: PatternParams, *, baby: bool) -> Pattern:
    craft = craft_for(spec)
    params = with_gauge(craft, params)
    gauge = resolve_gauge(params)
    if baby:
        size = params.talla if params.talla in BABY_SIZES else "3-6"
        circ_default, length_default = BABY_FOOT[size]
        circ_default *= BABY_EASE
        length_default += 1.0
    else:
        circ_default, length_default = ADULT_FOOT.get(params.talla.upper(), ADULT_FOOT["M"])
    circ = dimension(params, "circumference", circ_default)
    foot = dimension(params, "foot_length", length_default)
    spc = gauge.stitches_per_cm
    if craft.crochet:
        target = max(8, round_half_up(circ * spc))
        toe_rows, n = circle(craft, gauge, target)
        toe_rows[0] = Row(toe_rows[0].items, "acc.note.toe_ring")
    else:
        n_target = nearest_multiple(circ * spc, 4, minimum=12)
        start = max(8, 4 * round_half_up(n_target * 0.4 / 4))
        half = start // 2
        toe_rows = [
            Row(
                (Op(StitchKind.CAST_ON, times=start),), "acc.note.toe_cast_on", (("h", str(half)),)
            ),
            Row(plain(craft, start)),
        ]
        n = start
        while n < n_target:
            h = n // 2
            unit = (
                Op(StitchKind.KNIT),
                Op(StitchKind.M1L),
                *((Op(StitchKind.KNIT, times=h - 2),) if h > 2 else ()),
                Op(StitchKind.M1R),
                Op(StitchKind.KNIT),
            )
            toe_rows.append(
                Row((Repeat(2, unit),), "acc.note.toe_increase" if n == start else None)
            )
            n += 4
            if n < n_target:
                toe_rows.append(Row(plain(craft, n)))
    toe = build_section("toe", "section.toe", "round", 0, toe_rows, gauge)
    toe_worked = toe.meta["row_count"]
    heel_rows = max(2, gauge.rows_for_cm(foot * HEEL_SHARE))
    foot_rows = gauge.rows_for_cm(foot) - toe_worked - heel_rows
    if foot_rows < 1:
        raise ImpossibleProportionsError(
            "acc.error.too_short",
            cm=f"{foot:g}",
            min=f"{gauge.cm_for_rows(toe_worked + heel_rows + 1):.0f}",
        )
    sections: list[Section] = [
        toe,
        build_section(
            "foot",
            "section.foot",
            "round",
            n,
            [Row(plain(craft, n), "acc.note.foot" if i == 0 else None) for i in range(foot_rows)],
            gauge,
        ),
    ]
    instep = max(2, 2 * round_half_up(n * INSTEP_SHARE / 2))
    rest = n - instep
    if craft.crochet:
        heel: list[Row] = [
            Row(
                (*plain(craft, rest), Op(StitchKind.SKIP, times=instep)),
                "acc.note.heel_open_crochet",
                (("i", str(instep)), ("n", str(rest))),
            )
        ]
    else:
        lead = (n // 2 - instep) // 2
        heel = [
            Row(
                (
                    *((Op(StitchKind.KNIT, times=lead),) if lead else ()),
                    Op(StitchKind.BIND_OFF, times=instep),
                    Op(StitchKind.KNIT, times=rest - lead),
                ),
                "acc.note.heel_open",
                (("i", str(instep)),),
            )
        ]
    flat_id = None if craft.crochet else "garter"
    heel += pattern_rows(
        craft, rest, heel_rows - 1, round_mode=False, stitch_id=flat_id, note="acc.note.heel_rows"
    )
    sections.append(
        build_section("heel", "acc.section.heel", "flat", n, heel, gauge, bind_off=True)
    )
    cuff = instep + 2 * pick_up(gauge, heel_rows)
    cuff += cuff % 2
    cuff_rows = max(2, gauge.rows_for_cm(4.0 if baby else 2.5))
    sections.append(
        build_section(
            "cuff",
            "acc.section.ankle_cuff",
            "round",
            cuff,
            pattern_rows(
                craft,
                cuff,
                cuff_rows,
                round_mode=True,
                stitch_id=_rib(craft),
                note="acc.note.ankle_pickup",
                params=(("n", str(cuff)),),
            ),
            gauge,
            bind_off=True,
            meta={"picked": cuff},
        )
    )
    notes = [Note("acc.finish.heel_seam", {"n": rest // 2})]
    extra = 0.0
    if has_finish(spec, Finish.TIES):
        tie_cm = 30.0 if baby else 50.0
        sections.append(tie_section(craft, gauge, tie_cm))
        notes.append(Note("acc.finish.ties_bootie", {"cm": f"{round_half_up(tie_cm)}"}))
        extra = 2 * tie_cm / 100 * 4
    if not baby:
        notes.append(Note("acc.finish.non_slip", {}))
    notes.append(Note("acc.finish.make_pair", {}))
    measurements = [
        Measurement(
            key="circumference",
            value_cm=gauge.cm_for_stitches(n),
            target_cm=circ,
            tolerance_cm=repeat_tolerance(gauge, 1 if craft.crochet else 4, 1.5),
            kind="circumference",
        ),
        Measurement(
            key="foot_length",
            value_cm=gauge.cm_for_rows(toe_worked + foot_rows + heel_rows),
            target_cm=foot,
            tolerance_cm=_tol(gauge, 1.0),
            kind="length",
        ),
    ]
    family = "booties" if baby else "slippers"
    warnings = common_warnings(craft, params)
    if baby and params.talla not in BABY_SIZES:
        warnings.append(
            Warning("baby_size", "acc.warning.baby_size", severity="info", params={"size": "3-6"})
        )
    return Pattern(
        meta=meta(spec, params, family_name(craft, family), f"title.{family}"),
        spec=spec,
        params=params,
        sections=tuple(sections),
        measurements=fitted(measurements),
        materials=materials(
            craft,
            spec,
            params,
            2 * gauge.cm_for_stitches(n) * (foot + gauge.cm_for_rows(cuff_rows)),
            (
                "notion.crochet_hook" if craft.crochet else "notion.stitch_markers",
                "notion.tapestry_needle",
            ),
            extra_meters=extra,
        ),
        warnings=tuple(warnings),
        joins=(
            JoinCheck("join.toe", (CountRef("toe", "end"),), (CountRef("foot", "start"),)),
            JoinCheck("acc.join.heel", (CountRef("foot", "end"),), (CountRef("heel", "start"),)),
        ),
        finishing=tuple(notes),
    )


def generate_booties(spec: GarmentSpec, params: PatternParams) -> Pattern:
    return _toe_up(spec, params, baby=True)


# ---------------------------------------------------------------------------
# Pantuflas.
# ---------------------------------------------------------------------------

SLIPPER_TOE = 0.3  # ASUNCION: la punta fruncida ocupa el 30 % del largo
SLIPPER_SEAM = 0.25  # ASUNCION: la costura de arriba sigue un 25 % mas del largo


def _folded_slipper(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Pantufla clasica de dos agujas: un rectangulo en punto bobo (del
    talon a la punta) con la punta en elastico 2x2, que se frunce; se cosen
    los bordes arriba desde la punta y el borde de montaje doblado (talon)."""
    craft = craft_for(spec, knit_default="garter")
    gauge = resolve_gauge(params)
    circ_default, length_default = ADULT_FOOT.get(params.talla.upper(), ADULT_FOOT["M"])
    circ = dimension(params, "circumference", circ_default)
    foot = dimension(params, "foot_length", length_default)
    base = craft.stitch_id
    multiple = math.lcm(get_stitch(base).multiple, 4)
    width = nearest_multiple(circ * gauge.stitches_per_cm, multiple, minimum=16)
    toe_cm = foot * SLIPPER_TOE
    toe_rows = max(4, gauge.rows_for_cm(toe_cm))
    sole_rows = gauge.rows_for_cm(foot) - toe_rows
    if sole_rows < 4:
        raise ImpossibleProportionsError(
            "acc.error.too_short", cm=f"{foot:g}", min=f"{gauge.cm_for_rows(toe_rows + 4):.0f}"
        )
    sole = build_section(
        "sole",
        "acc.section.slipper",
        "flat",
        0,
        [
            cast_on_row(craft, width, round_mode=False),
            *pattern_rows(craft, width, sole_rows, round_mode=False, note="acc.note.slipper_body"),
        ],
        gauge,
    )
    toe = build_section(
        "toe",
        "section.toe",
        "flat",
        width,
        pattern_rows(
            craft,
            width,
            toe_rows,
            round_mode=False,
            first=sole_rows + 1,
            stitch_id="rib_2x2",
            note="acc.note.slipper_toe",
        ),
        gauge,
        end_note_keys=("acc.note.gather_toe",),
    )
    seam_cm = foot * (SLIPPER_TOE + SLIPPER_SEAM)
    return Pattern(
        meta=meta(spec, params, "slippers", "title.slippers"),
        spec=spec,
        params=params,
        sections=(sole, toe),
        measurements=fitted(
            [
                Measurement(
                    key="circumference",
                    value_cm=gauge.cm_for_stitches(width),
                    target_cm=circ,
                    tolerance_cm=repeat_tolerance(gauge, multiple, 1.5),
                    kind="circumference",
                ),
                Measurement(
                    key="foot_length",
                    value_cm=gauge.cm_for_rows(sole_rows + toe_rows),
                    target_cm=foot,
                    tolerance_cm=_tol(gauge, 1.0),
                    kind="length",
                ),
            ]
        ),
        materials=materials(
            craft, spec, params, 2 * circ * foot, ("notion.tapestry_needle", "notion.tape_measure")
        ),
        warnings=tuple(common_warnings(craft, params)),
        joins=(
            JoinCheck("acc.join.slipper", (CountRef("sole", "end"),), (CountRef("toe", "start"),)),
        ),
        finishing=(
            Note("acc.finish.slipper_seam", {"cm": f"{round_half_up(seam_cm)}"}),
            Note("acc.finish.slipper_heel", {}),
            Note("acc.finish.non_slip", {}),
            Note("acc.finish.make_pair", {}),
        ),
    )


def generate_slippers(spec: GarmentSpec, params: PatternParams) -> Pattern:
    craft = craft_for(spec)
    if craft.crochet:
        return _toe_up(spec, params, baby=False)
    return _folded_slipper(spec, params)
