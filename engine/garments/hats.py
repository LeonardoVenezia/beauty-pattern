"""Gorros por estilo (D038), pasamontanas y vincha, en dos agujas y crochet.

Estilos (`spec.estilo_gorro`):
- beanie, slouchy, earflap (chullo) y beret (boina) en dos agujas: de abajo
  hacia arriba (borde, cuerpo, corona en gajos o en elastico).
- bucket (piluso) y brimmed (capelina, casquete de red): de arriba hacia
  abajo, coronilla plana, costados rectos y ala con aumentos.
- todos los de crochet: de arriba hacia abajo desde un anillo magico.
- bonnet (capota): en plano alrededor de la cara y despues la nuca, con lazos.

Acabados: pompon (medida, vueltas al molde y metros), orejeras (levantadas
del borde) y lazos (i-cord o cadena). Todo numero sale de este codigo; las
proporciones sin fuente estan marcadas ASUNCION (ver docs/fuentes.md).
"""

from __future__ import annotations

import math
from collections.abc import Callable

from engine.distribution import split_even
from engine.garments.acc_kit import (
    Craft,
    Row,
    build_section,
    cast_on_row,
    common_warnings,
    craft_for,
    dimension,
    family_name,
    fitted,
    flat_rate,
    has_finish,
    head_cm,
    is_baby,
    is_mesh,
    materials,
    mesh_items,
    meta,
    nearest_multiple,
    pattern_rows,
    pick_up,
    plain,
    pompom,
    repeat_tolerance,
    scale,
    shape_items,
    tie_section,
    with_gauge,
)
from engine.garments.base import ImpossibleProportionsError
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
from engine.spec import Finish, GarmentSpec, HatStyle, PatternParams, Technique, resolve_gauge
from engine.stitches.catalog import expand_row, get_stitch
from engine.stitches.kinds import StitchKind

# ASUNCION: corona en gajos (8 es lo habitual; 4-10 segun la cantidad de
# puntos) con disminuciones cada 2 vueltas (convencion de gorros de jersey).
HAT_SECTORS = (8, 7, 9, 6, 10, 5, 4)
CROWN_SHARE = 0.35  # ASUNCION: la corona ocupa ~1/3 del alto del gorro

# Holgura (fraccion del contorno de cabeza). Gorro de punto: 90 % (borde
# elastico, practica habitual de patrones publicados). ASUNCION en el resto:
BEANIE_EASE = 0.9
CROCHET_EASE = 0.92  # el crochet cede menos (docs/fuentes.md)
SLOUCHY_EASE = 1.1  # el cuerpo del slouchy, que cae flojo hacia atras
BERET_DISC = 1.5  # contorno del disco de la boina (~27 cm de diametro en M)
BUCKET_EASE = 1.0  # el piluso apoya sin apretar
BRIMMED_EASE = 0.97
# Ala: fraccion de los aumentos de un circulo plano. 1 = plana, 0 = recta.
BUCKET_FLARE = 0.5  # ala caida (~60 grados)
BRIMMED_FLARE = 0.8  # ala casi plana de capelina


def _title(craft: Craft, style: HatStyle) -> str:
    if style is HatStyle.BEANIE:
        return "title.hat_crochet" if craft.crochet else "title.hat"
    return f"title.hat_{style.value}"


def _family(craft: Craft, style: HatStyle) -> str:
    base = "hat" if style is HatStyle.BEANIE else f"hat_{style.value}"
    return family_name(craft, base)


def hat_style(spec: GarmentSpec) -> HatStyle:
    style = spec.estilo_gorro or HatStyle.BEANIE
    if style is HatStyle.BEANIE and has_finish(spec, Finish.EARFLAPS):
        return HatStyle.EARFLAP
    return style


# ---------------------------------------------------------------------------
# Coronas (las de siempre del gorro de dos agujas).
# ---------------------------------------------------------------------------


def rib_crown(stitches: int) -> list[Row]:
    """Corona clasica de gorro en elastico 2x2: las disminuciones se hacen
    dentro del elastico (primero en los reveses, despues en los derechos), sin
    cortar las columnas. Desde `stitches` hasta stitches/8."""
    n = stitches // 4
    k, p = StitchKind.KNIT, StitchKind.PURL
    rows = [
        Row((Repeat(n, (Op(k, times=2), Op(StitchKind.P2TOG))),), "pattern.note.rib_crown_purls"),
        Row((Repeat(n, (Op(k, times=2), Op(p))),)),
        Row((Repeat(n, (Op(StitchKind.K2TOG), Op(p))),), "pattern.note.rib_crown_knits"),
        Row((Repeat(n, (Op(k), Op(p))),)),
        Row((Op(StitchKind.K2TOG, times=n),), "pattern.note.rib_crown_last"),
    ]
    if n % 2 == 0 and n > 8:  # una vuelta mas de 2 juntos: la coronilla cierra sin agujero
        rows.append(Row((Op(StitchKind.K2TOG, times=n // 2),)))
    return rows


def sector_crown(stitches: int, sectors: int, max_rows: int) -> list[Row]:
    """Corona en gajos: una disminucion por gajo por vuelta de disminucion
    hasta que queda 1 punto por gajo. Primero cada 2 vueltas y, si no entra en
    `max_rows`, el final en todas las vueltas (como los patrones publicados)."""
    per = stitches // sectors
    decreases = per - 1
    spare = max(0, min(decreases - 1, max_rows - decreases))
    rows: list[Row] = []
    while per > 1:
        knits = (Op(StitchKind.KNIT, times=per - 2),) if per > 2 else ()
        rows.append(
            Row((Repeat(sectors, (*knits, Op(StitchKind.K2TOG))),), "pattern.note.hat_crown")
        )
        per -= 1
        if per > 1 and spare:
            spare -= 1
            rows.append(Row((Op(StitchKind.KNIT, times=per * sectors),)))
    return rows


def choose_sectors(options: tuple[int, ...], fit: Callable[[int], int], wanted: float, spc: float) -> int:
    """Gajos de la corona: el primero de `options` (orden de preferencia, 8
    primero) cuyo conteo queda a menos de 1 cm del mejor posible. Asi no se
    elige una corona de 4 gajos solo porque cierra medio punto mas justo."""
    best = min(abs(fit(n) - wanted) for n in options)
    return next(n for n in options if abs(fit(n) - wanted) <= best + spc)


def decrease_to(
    craft: Craft, n: int, per: int, stop: int, *, every: int = 1, note: str | None = None
) -> tuple[list[Row], int]:
    """Disminuir `per` pts por vuelta (cada `every` vueltas) hasta `stop`."""
    rows: list[Row] = []
    while n > stop:
        k = min(per, n - stop, n // 2)
        rows.append(Row(shape_items(craft, n, -k), note if not rows else None))
        n -= k
        for _ in range(every - 1):
            if n > stop:
                rows.append(Row(plain(craft, n)))
    return rows, n


def increase_to(
    craft: Craft,
    n: int,
    per: int,
    target: int,
    *,
    every: int = 1,
    note: str | None = None,
    later: str | None = None,
) -> tuple[list[Row], int]:
    """Aumentar `per` pts por vuelta (la ultima, lo que falte) hasta `target`."""
    rows: list[Row] = []
    while n < target:
        k = min(per, target - n, n)
        rows.append(Row(shape_items(craft, n, k), note if not rows else later))
        n += k
        for _ in range(every - 1):
            if n < target:
                rows.append(Row(plain(craft, n)))
    return rows, n


def circle(craft: Craft, gauge: Gauge, target: int) -> tuple[list[Row], int]:
    """Coronilla plana desde el centro hasta `target` pts.

    Crochet: anillo con los aumentos de un circulo plano y aumentos en todas
    las vueltas. Dos agujas: 8 pts y 8 aumentos cada 2 vueltas (circulo
    plano clasico). La ultima vuelta suma solo los que faltan."""
    if craft.crochet:
        per = max(6, min(12, round(flat_rate(gauge))))
        start: list[Row] = [Row((Op(StitchKind.RING, width=per),))]
        rows, n = increase_to(
            craft,
            per,
            per,
            max(target, per),
            note="pattern.note.crochet_crown",
            later="pattern.note.circle_increase",
        )
        return start + rows, n
    per = 8
    start = [
        Row((Op(StitchKind.CAST_ON, times=per),), "acc.note.crown_cast_on"),
        Row(plain(craft, per)),
    ]
    rows, n = increase_to(
        craft, per, per, max(target, per), every=2, note="acc.note.crown_increase"
    )
    return start + rows, n


# ---------------------------------------------------------------------------
# Terminaciones comunes (orejeras, lazos, pompon).
# ---------------------------------------------------------------------------


def earflap_section(craft: Craft, gauge: Gauge, params: PatternParams, brim: int) -> Section:
    """Orejera: se levanta del borde de montaje y se teje en plano hacia
    abajo, disminuyendo en los dos extremos hasta 4 o 5 pts.

    ASUNCION: orejera = 20 % del contorno; entre las dos, atras, 15 %; largo
    9 cm para 56 cm de cabeza (patrones de chullo publicados)."""
    flap = max(8, round_half_up(brim * 0.2))
    back = 2 * max(1, round_half_up(brim * 0.075))
    front = brim - 2 * flap - back
    end = 4 if flap % 2 == 0 else 5
    decreases = (flap - end) // 2
    straight_min = 1 if craft.crochet else 2
    rows_total = max(straight_min + 1, gauge.rows_for_cm(scale(params, 9.0)))
    # Primero disminuir cada 2 hileras; si el largo no alcanza, en todas, y si
    # tampoco, la orejera termina mas ancha (el largo manda).
    every_other = rows_total - straight_min >= 2 * decreases
    if not every_other:
        decreases = min(decreases, rows_total - straight_min)
    straight = rows_total - (2 * decreases if every_other else decreases)
    pickup = Row(
        plain(craft, flap) if craft.crochet else (Op(StitchKind.KNIT, times=flap),),
        "acc.note.flap_pickup",
        (("a", str(back // 2)), ("f", str(flap)), ("g", str(front)), ("n", str(flap))),
    )
    rows = [pickup]
    rows += [Row(plain(craft, flap)) for _ in range(straight - 1)]
    n = flap
    for index in range(decreases):
        if craft.crochet:
            items: tuple[Item, ...] = (
                (Op(craft.dec), *plain(craft, n - 4), Op(craft.dec))
                if n > 4
                else (Op(craft.dec, times=2),)
            )
        else:
            inner = (Op(StitchKind.KNIT, times=n - 6),) if n > 6 else ()
            items = (
                Op(StitchKind.KNIT),
                Op(StitchKind.SSK),
                *inner,
                Op(StitchKind.K2TOG),
                Op(StitchKind.KNIT),
            )
        rows.append(Row(items, "acc.note.flap_decrease" if index == 0 else None))
        n -= 2
        if every_other:
            rows.append(Row(plain(craft, n)))
    return build_section(
        "earflap",
        "acc.section.earflap",
        "flat",
        flap,
        rows,
        gauge,
        bind_off=True,
        note_keys=(
            "acc.note.make_two",
            "acc.note.flap_crochet" if craft.crochet else "acc.note.flap_garter",
        ),
        meta={"front_gap": front, "back_gap": back},
    )


def hat_finishing(
    spec: GarmentSpec,
    gauge: Gauge,
    params: PatternParams,
    sections: list[Section],
    craft: Craft,
    *,
    ties_default: bool = False,
) -> tuple[list[Note], float]:
    """Pompon, borlas y lazos pedidos en `acabados`. Devuelve (notas, metros
    extra de hilo)."""
    notes: list[Note] = []
    extra = 0.0
    if has_finish(spec, Finish.TIES) or ties_default:
        length = scale(params, 30.0)
        sections.append(tie_section(craft, gauge, length))
        notes.append(Note("acc.finish.ties", {"cm": f"{round_half_up(length)}"}))
        extra += 2 * length / 100 * (5 if not craft.crochet else 3)
    if has_finish(spec, Finish.POMPOM):
        diameter = round(scale(params, 8.0) * 2) / 2  # ASUNCION: 8 cm en un gorro adulto
        made = pompom(gauge, diameter)
        notes.append(
            Note(
                "acc.finish.pompom",
                {
                    "d": f"{made.diameter_cm:g}",
                    "hole": f"{made.diameter_cm / 3:.1f}",
                    "wraps": made.wraps,
                    "m": f"{made.meters:g}",
                },
            )
        )
        extra += made.meters
    if has_finish(spec, Finish.FRINGE) and any(s.id == "earflap" for s in sections):
        notes.append(Note("acc.finish.tassels", {"cm": f"{round_half_up(scale(params, 8.0))}"}))
        extra += 6.0
    return notes, extra


def _length_tolerance(gauge: Gauge, base: float = 1.5) -> float:
    return max(base, 1.0 / gauge.rows_per_cm)


# ---------------------------------------------------------------------------
# Dos agujas, de abajo hacia arriba: beanie, slouchy, chullo y boina.
# ---------------------------------------------------------------------------


def _bottom_up(spec: GarmentSpec, params: PatternParams, style: HatStyle) -> Pattern:
    craft = craft_for(spec)
    gauge = resolve_gauge(params)
    spc = gauge.stitches_per_cm
    head = head_cm(params)
    base = craft.stitch_id
    ribbed = base == "rib_2x2" or (base.startswith("rib") and spec.punto_base is not None)
    if ribbed:
        base = "rib_2x2"
    knit = Craft(False, StitchKind.KNIT, base)
    brim_id = "garter" if style is HatStyle.EARFLAP and not ribbed else "rib_2x2"
    brim_wanted = head * BEANIE_EASE
    brim = nearest_multiple(brim_wanted * spc, get_stitch(brim_id).multiple, minimum=16)
    body_factor = {HatStyle.SLOUCHY: SLOUCHY_EASE, HatStyle.BERET: BERET_DISC}.get(
        style, BEANIE_EASE
    )
    wanted = head * body_factor * spc
    if ribbed:
        sectors = 4
        body = nearest_multiple(wanted, 4, minimum=16)
    else:

        def fit(n: int) -> int:
            return nearest_multiple(
                wanted,
                math.lcm(get_stitch(base).multiple, n),
                minimum=2 * math.lcm(get_stitch(base).multiple, n),
            )

        options: tuple[int, ...] = HAT_SECTORS
        if style is HatStyle.BERET:
            # La boina se cierra plana: gajos ~ aumentos de un circulo plano
            # cada 2 vueltas (8-10 en lana DK).
            options = tuple(sorted(range(6, 13), key=lambda s: abs(s - 2 * flat_rate(gauge)))[:3])
        sectors = choose_sectors(options, fit, wanted, spc)
        body = fit(sectors)
    if body_factor == BEANIE_EASE and body % get_stitch(brim_id).multiple == 0:
        brim = body  # sin vuelta de ajuste si el borde ya cierra con el cuerpo
    adult_height = {HatStyle.SLOUCHY: 28.0, HatStyle.EARFLAP: 21.0}.get(style, 22.0)
    height = dimension(
        params,
        "length",
        scale(params, adult_height) if (is_baby(params) or style is not HatStyle.BEANIE) else 22.0,
    )
    brim_cm = scale(params, 3.0 if style in {HatStyle.EARFLAP, HatStyle.BERET} else 4.0)
    brim_rows = max(2, gauge.rows_for_cm(brim_cm))
    if style is HatStyle.BERET:
        crown_rows = sector_crown(body, sectors, 10_000) if not ribbed else rib_crown(body)
    else:
        crown_rows = (
            rib_crown(body)
            if ribbed
            else sector_crown(body, sectors, gauge.rows_for_cm(height * CROWN_SHARE))
        )
    crown_cm = gauge.cm_for_rows(len(crown_rows))
    if style is HatStyle.BERET:
        body_rows = max(2, gauge.rows_for_cm(scale(params, 4.0)))
    else:
        if height <= brim_cm + crown_cm + 1:
            raise ImpossibleProportionsError(
                "acc.error.too_short", cm=f"{height:g}", min=f"{brim_cm + crown_cm + 1:.0f}"
            )
        body_rows = max(1, gauge.rows_for_cm(height - brim_cm - crown_cm))
    sections: list[Section] = []
    brim_section = build_section(
        "brim",
        "section.brim",
        "round",
        0,
        [
            cast_on_row(knit, brim, round_mode=True),
            *pattern_rows(
                knit,
                brim,
                brim_rows,
                round_mode=True,
                stitch_id=brim_id,
                note="acc.note.brim_garter" if brim_id == "garter" else "pattern.note.hat_brim",
            ),
        ],
        gauge,
    )
    sections.append(brim_section)
    body_rows_list: list[Row] = []
    if body != brim:
        body_rows_list.append(
            Row(shape_items(knit, brim, body - brim), "acc.note.adjust_round", (("n", str(body)),))
        )
    plain_count = max(1, body_rows - len(body_rows_list))
    body_rows_list += pattern_rows(
        knit, body, plain_count, round_mode=True, note="pattern.note.hat_body"
    )
    sections.append(build_section("body", "section.body", "round", brim, body_rows_list, gauge))
    sections.append(
        build_section(
            "crown", "section.crown", "round", body, crown_rows, gauge, gather=True, target=True
        )
    )
    measurements = [
        Measurement(
            key="head", value_cm=head, target_cm=head, tolerance_cm=0.1, kind="circumference"
        ),
        Measurement(
            key="circumference",
            value_cm=gauge.cm_for_stitches(brim),
            target_cm=brim_wanted,
            tolerance_cm=repeat_tolerance(gauge, get_stitch(brim_id).multiple, 2.5),
            kind="circumference",
        ),
    ]
    if style is HatStyle.SLOUCHY:
        measurements.append(
            Measurement(
                key="body_circumference",
                value_cm=gauge.cm_for_stitches(body),
                target_cm=head * SLOUCHY_EASE,
                tolerance_cm=repeat_tolerance(
                    gauge, math.lcm(get_stitch(base).multiple, sectors), 2.5
                ),
                kind="circumference",
            )
        )
    total_rows = brim_rows + len(body_rows_list) + len(crown_rows)
    if style is HatStyle.BERET:
        disc = gauge.cm_for_stitches(body) / math.pi
        measurements.append(
            Measurement(
                key="diameter",
                value_cm=disc,
                target_cm=head * BERET_DISC / math.pi,
                tolerance_cm=max(
                    1.0,
                    repeat_tolerance(gauge, math.lcm(get_stitch(base).multiple, sectors), 1.0)
                    / math.pi,
                ),
                kind="width",
            )
        )
    else:
        measurements.append(
            Measurement(
                key="length",
                value_cm=gauge.cm_for_rows(total_rows),
                target_cm=height,
                tolerance_cm=_length_tolerance(gauge),
                kind="length",
            )
        )
    joins = [
        JoinCheck("join.brim", (CountRef("brim", "end"),), (CountRef("body", "start"),)),
        JoinCheck("join.crown", (CountRef("body", "end"),), (CountRef("crown", "start"),)),
    ]
    if style is HatStyle.EARFLAP:
        flap = earflap_section(knit, gauge, params, brim)
        sections.append(flap)
        measurements.append(
            Measurement(
                key="flap_length",
                value_cm=gauge.cm_for_rows(flap.meta["row_count"]),
                target_cm=scale(params, 9.0),
                tolerance_cm=_length_tolerance(gauge),
                kind="length",
            )
        )
    notes, extra = hat_finishing(spec, gauge, params, sections, knit)
    area = gauge.cm_for_stitches(body) * gauge.cm_for_rows(total_rows)
    if style is HatStyle.EARFLAP:
        area += (
            2
            * 0.7
            * gauge.cm_for_stitches(sections[3].start_stitches)
            * gauge.cm_for_rows(sections[3].meta["row_count"])
        )
    warnings = common_warnings(knit, params)
    if style is HatStyle.BERET:
        warnings.append(Warning("beret_blocking", "acc.warning.beret_blocking", severity="info"))
    return Pattern(
        meta=meta(spec, params, _family(knit, style), _title(knit, style)),
        spec=spec,
        params=params,
        sections=tuple(sections),
        measurements=fitted(measurements),
        materials=materials(
            knit,
            spec,
            params,
            area,
            ("notion.stitch_markers", "notion.tapestry_needle", "notion.tape_measure"),
            extra_meters=extra,
        ),
        warnings=tuple(warnings),
        joins=tuple(joins),
        finishing=tuple(notes),
    )


# ---------------------------------------------------------------------------
# De arriba hacia abajo: todos los de crochet, y piluso y capelina de agujas.
# ---------------------------------------------------------------------------


def _top_down(spec: GarmentSpec, params: PatternParams, style: HatStyle) -> Pattern:
    mesh = is_mesh(spec) and spec.tecnica is Technique.CROCHET
    craft = craft_for(spec, crochet_default="crochet_dc" if mesh else "crochet_sc")
    if mesh:
        craft = Craft(True, StitchKind.DC, "crochet_dc")
    elif not craft.crochet:
        craft = Craft(False, StitchKind.KNIT, "stockinette")
    if craft.crochet and spec.punto_base is None and not mesh:
        craft = Craft(True, StitchKind.HDC, "crochet_hdc")  # ASUNCION: el mas usado en gorros
    params = with_gauge(craft, params)
    gauge = resolve_gauge(params)
    spc = gauge.stitches_per_cm
    head = head_cm(params)
    ease = {
        HatStyle.SLOUCHY: SLOUCHY_EASE,
        HatStyle.BERET: BERET_DISC,
        HatStyle.BUCKET: BUCKET_EASE,
        HatStyle.BRIMMED: BRIMMED_EASE,
    }.get(style, CROCHET_EASE if craft.crochet else BEANIE_EASE)
    crown_target = round_half_up(head * ease * spc)
    crown_rows, n = circle(craft, gauge, crown_target)
    sections: list[Section] = [
        build_section("crown", "section.crown", "round", 0, crown_rows, gauge)
    ]
    crown_worked = sections[0].meta["row_count"]
    measurements: list[Measurement] = [
        Measurement(
            key="head", value_cm=head, target_cm=head, tolerance_cm=0.1, kind="circumference"
        )
    ]
    band_target = round_half_up(head * CROCHET_EASE * spc)
    if style in {HatStyle.SLOUCHY, HatStyle.BERET}:
        band_cm = scale(params, 3.0 if style is HatStyle.BERET else 4.0)
        default_length = scale(params, 27.0) if style is HatStyle.SLOUCHY else 0.0
        band_rows = max(2, gauge.rows_for_cm(band_cm))
        if style is HatStyle.BERET:
            side_rows = max(2, gauge.rows_for_cm(scale(params, 2.0)))
        else:
            length = dimension(params, "length", default_length)
            side_rows = gauge.rows_for_cm(length) - crown_worked - 1 - band_rows
            if side_rows < 1:
                raise ImpossibleProportionsError(
                    "acc.error.too_short",
                    cm=f"{length:g}",
                    min=f"{gauge.cm_for_rows(crown_worked + 2 + band_rows):.0f}",
                )
        sides = [
            Row(mesh_items(n) if mesh else plain(craft, n), "acc.note.sides" if i == 0 else None)
            for i in range(side_rows)
        ]
        if style is HatStyle.BERET:
            per = max(6, min(12, round(flat_rate(gauge))))
            down, m = decrease_to(craft, n, per, band_target, note="acc.note.beret_decrease")
        else:
            down = [
                Row(
                    shape_items(craft, n, band_target - n),
                    "acc.note.adjust_round",
                    (("n", str(band_target)),),
                )
            ]
            m = band_target
        sides += down
        sections.append(build_section("body", "section.body", "round", n, sides, gauge))
        sections.append(
            build_section(
                "brim",
                "section.brim",
                "round",
                m,
                [
                    Row(plain(craft, m), "acc.note.band_crochet" if i == 0 else None)
                    for i in range(band_rows)
                ],
                gauge,
                bind_off=True,
            )
        )
        measurements.append(
            Measurement(
                key="circumference",
                value_cm=gauge.cm_for_stitches(m),
                target_cm=head * CROCHET_EASE,
                tolerance_cm=2.5,
                kind="circumference",
            )
        )
        if style is HatStyle.BERET:
            measurements.append(
                Measurement(
                    key="diameter",
                    value_cm=gauge.cm_for_stitches(n) / math.pi,
                    target_cm=head * BERET_DISC / math.pi,
                    tolerance_cm=1.0,
                    kind="width",
                )
            )
        else:
            measurements.append(
                Measurement(
                    key="body_circumference",
                    value_cm=gauge.cm_for_stitches(n),
                    target_cm=head * SLOUCHY_EASE,
                    tolerance_cm=2.5,
                    kind="circumference",
                )
            )
            total = crown_worked + len(sides) + band_rows
            measurements.append(
                Measurement(
                    key="length",
                    value_cm=gauge.cm_for_rows(total),
                    target_cm=length,
                    tolerance_cm=_length_tolerance(gauge),
                    kind="length",
                )
            )
    elif style in {HatStyle.BUCKET, HatStyle.BRIMMED}:
        side_cm = dimension(
            params, "height", scale(params, 9.0 if style is HatStyle.BUCKET else 10.0)
        )
        brim_cm = dimension(params, "brim", scale(params, 6.0 if style is HatStyle.BUCKET else 9.0))
        side_rows = max(2, gauge.rows_for_cm(side_cm))
        sides = []
        for i in range(side_rows):
            if mesh:
                items = mesh_items(n)
            elif craft.crochet:
                items = plain(craft, n)
            else:
                items = (Op(StitchKind.KNIT, times=n),)
            sides.append(
                Row(items, ("acc.note.mesh" if mesh else "acc.note.sides") if i == 0 else None)
            )
        sections.append(build_section("body", "section.body", "round", n, sides, gauge))
        brim_rows = max(2, gauge.rows_for_cm(brim_cm))
        flare = BUCKET_FLARE if style is HatStyle.BUCKET else BRIMMED_FLARE
        increases = round_half_up(flare * flat_rate(gauge) * brim_rows)
        brim_list: list[Row] = []
        m = n
        if craft.crochet:
            for i, k in enumerate(split_even(increases, brim_rows)):
                brim_list.append(
                    Row(shape_items(craft, m, min(k, m)), "acc.note.brim_flare" if i == 0 else None)
                )
                m += min(k, m)
        else:
            inc_rounds = (brim_rows + 1) // 2
            ks = split_even(increases, inc_rounds)
            for i in range(brim_rows):
                if i % 2 == 0:
                    k = min(ks[i // 2], m)
                    brim_list.append(
                        Row(
                            shape_items(craft, m, k), "acc.note.brim_flare_knit" if i == 0 else None
                        )
                    )
                    m += k
                else:
                    brim_list.append(Row((Op(StitchKind.PURL, times=m),)))
        sections.append(
            build_section(
                "brim", "acc.section.hat_brim", "round", n, brim_list, gauge, bind_off=True
            )
        )
        measurements += [
            Measurement(
                key="circumference",
                value_cm=gauge.cm_for_stitches(n),
                target_cm=head * ease,
                tolerance_cm=2.5,
                kind="circumference",
            ),
            Measurement(
                key="height",
                value_cm=gauge.cm_for_rows(side_rows),
                target_cm=side_cm,
                tolerance_cm=_length_tolerance(gauge, 1.0),
                kind="length",
            ),
            Measurement(
                key="brim_width",
                value_cm=gauge.cm_for_rows(brim_rows),
                target_cm=brim_cm,
                tolerance_cm=_length_tolerance(gauge, 1.0),
                kind="length",
            ),
        ]
    else:  # beanie y chullo de crochet
        length = dimension(
            params, "length", scale(params, 21.0 if style is HatStyle.BEANIE else 20.0)
        )
        side_rows = gauge.rows_for_cm(length) - crown_worked
        if side_rows < 1:
            raise ImpossibleProportionsError(
                "acc.error.too_short",
                cm=f"{length:g}",
                min=f"{gauge.cm_for_rows(crown_worked + 1):.0f}",
            )
        sides = [
            Row(
                mesh_items(n) if mesh else plain(craft, n),
                ("acc.note.mesh" if mesh else "pattern.note.plain") if i == 0 else None,
            )
            for i in range(side_rows)
        ]
        sections.append(
            build_section("body", "section.body", "round", n, sides, gauge, bind_off=True)
        )
        measurements += [
            Measurement(
                key="circumference",
                value_cm=gauge.cm_for_stitches(n),
                target_cm=head * ease,
                tolerance_cm=2.5,
                kind="circumference",
            ),
            Measurement(
                key="length",
                value_cm=gauge.cm_for_rows(crown_worked + side_rows),
                target_cm=length,
                tolerance_cm=_length_tolerance(gauge),
                kind="length",
            ),
        ]
        if style is HatStyle.EARFLAP:
            flap = earflap_section(craft, gauge, params, n)
            sections.append(flap)
            measurements.append(
                Measurement(
                    key="flap_length",
                    value_cm=gauge.cm_for_rows(flap.meta["row_count"]),
                    target_cm=scale(params, 9.0),
                    tolerance_cm=_length_tolerance(gauge),
                    kind="length",
                )
            )
    joins = [JoinCheck("join.crown", (CountRef("crown", "end"),), (CountRef("body", "start"),))]
    if any(s.id == "brim" for s in sections):
        joins.append(
            JoinCheck("join.brim", (CountRef("body", "end"),), (CountRef("brim", "start"),))
        )
    notes, extra = hat_finishing(spec, gauge, params, sections, craft)
    if style is HatStyle.BRIMMED:
        notes.append(Note("acc.finish.stiff_brim", {}))
    worked = sum(s.meta.get("row_count", 0) for s in sections if s.id in {"crown", "body", "brim"})
    widest = max(s.end_stitches for s in sections)
    area = 0.75 * gauge.cm_for_stitches(widest) * gauge.cm_for_rows(worked)
    warnings = common_warnings(craft, params)
    if mesh:
        warnings.append(Warning("mesh_hat", "acc.warning.mesh", severity="info"))
    return Pattern(
        meta=meta(spec, params, _family(craft, style), _title(craft, style)),
        spec=spec,
        params=params,
        sections=tuple(sections),
        measurements=fitted(measurements),
        materials=materials(
            craft,
            spec,
            params,
            area,
            (
                "notion.crochet_hook" if craft.crochet else "notion.stitch_markers",
                "notion.stitch_markers" if craft.crochet else "notion.tape_measure",
                "notion.tapestry_needle",
            ),
            extra_meters=extra,
        ),
        warnings=tuple(warnings),
        joins=tuple(joins),
        finishing=tuple(notes),
    )


# ---------------------------------------------------------------------------
# Capota (bonnet): en plano alrededor de la cara y despues la nuca.
# ---------------------------------------------------------------------------

BONNET_FACE = 0.65  # ASUNCION: borde de la cara (de cuello a cuello por arriba) / contorno
BONNET_DEPTH = 0.3  # ASUNCION: profundidad (de la frente a la nuca) / contorno


def _bonnet(spec: GarmentSpec, params: PatternParams) -> Pattern:
    craft = craft_for(spec, knit_default="garter", crochet_default="crochet_hdc")
    params = with_gauge(craft, params)
    gauge = resolve_gauge(params)
    head = head_cm(params)
    face_cm = dimension(params, "width", head * BONNET_FACE)
    depth_cm = dimension(params, "length", head * BONNET_DEPTH)
    multiple = math.lcm(craft.multiple, 2)
    width = nearest_multiple(face_cm * gauge.stitches_per_cm, multiple, minimum=3 * multiple)
    side = nearest_multiple(width / 3, craft.multiple)
    center = width - 2 * side
    band_rows = max(2, gauge.rows_for_cm(scale(params, 2.0))) if not craft.crochet else 0
    rows_total = max(band_rows + 2, gauge.rows_for_cm(depth_cm))
    first: list[Row] = [cast_on_row(craft, width, round_mode=False)]
    if craft.crochet:
        first += pattern_rows(
            craft, width, rows_total, round_mode=False, note="pattern.note.crochet_flat"
        )
    else:
        first += pattern_rows(
            craft, width, band_rows, round_mode=False, stitch_id="garter", note="acc.note.face_band"
        )
        first += pattern_rows(
            craft,
            width,
            rows_total - band_rows,
            round_mode=False,
            first=band_rows + 1,
            note="acc.note.bonnet_body",
        )
    sides_section = build_section("face", "acc.section.bonnet_face", "flat", 0, first, gauge)
    back_rows = max(2, gauge.rows_for_cm(gauge.cm_for_stitches(side)))
    if craft.crochet:
        back: list[Row] = [
            Row(
                (
                    Op(StitchKind.SKIP, times=side),
                    *plain(craft, center),
                    Op(StitchKind.SKIP, times=side),
                ),
                "acc.note.bonnet_back_crochet",
                (("s", str(side)), ("c", str(center))),
            )
        ]
        back += [Row(plain(craft, center)) for _ in range(back_rows - 1)]
    else:
        stitch = get_stitch(craft.stitch_id)
        back = [
            Row(
                (
                    Op(StitchKind.BIND_OFF, times=side),
                    *expand_row(stitch, width - side, rows_total + 1),
                ),
                "acc.note.bonnet_back",
                (("s", str(side)),),
            ),
            Row((Op(StitchKind.BIND_OFF, times=side), *expand_row(stitch, center, rows_total + 2))),
        ]
        back += pattern_rows(craft, center, back_rows - 1, round_mode=False, first=rows_total + 3)
    back_section = build_section(
        "back", "acc.section.bonnet_back", "flat", width, back, gauge, bind_off=True
    )
    sections = [sides_section, back_section]
    tie_cm = scale(params, 30.0)
    sections.append(tie_section(craft, gauge, tie_cm))
    notes = [
        Note("acc.finish.bonnet_seam", {"s": side, "c": center}),
        Note("acc.finish.ties_bonnet", {"cm": f"{round_half_up(tie_cm)}"}),
    ]
    extra = 2 * tie_cm / 100 * (3 if craft.crochet else 5)
    if has_finish(spec, Finish.POMPOM):
        made = pompom(gauge, round(scale(params, 6.0) * 2) / 2)
        notes.append(
            Note(
                "acc.finish.pompom",
                {
                    "d": f"{made.diameter_cm:g}",
                    "hole": f"{made.diameter_cm / 3:.1f}",
                    "wraps": made.wraps,
                    "m": f"{made.meters:g}",
                },
            )
        )
        extra += made.meters
    # Hileras de la pieza del centro (en agujas, la primera cierra un costado).
    seam_back = gauge.cm_for_rows(back_rows)
    measurements = [
        Measurement(
            key="head", value_cm=head, target_cm=head, tolerance_cm=0.1, kind="circumference"
        ),
        Measurement(
            key="width",
            value_cm=gauge.cm_for_stitches(width),
            target_cm=face_cm,
            tolerance_cm=repeat_tolerance(gauge, multiple, 1.5),
            kind="width",
        ),
        Measurement(
            key="length",
            value_cm=gauge.cm_for_rows(rows_total),
            target_cm=depth_cm,
            tolerance_cm=_length_tolerance(gauge),
            kind="length",
        ),
        # Costura de la nuca: el largo de la pieza del centro tiene que cubrir
        # lo que mide cada costado cerrado.
        Measurement(
            key="back_seam",
            value_cm=seam_back,
            target_cm=gauge.cm_for_stitches(side),
            tolerance_cm=_length_tolerance(gauge, 1.0),
            kind="length",
        ),
    ]
    area = gauge.cm_for_stitches(width) * depth_cm + gauge.cm_for_stitches(center) * seam_back
    return Pattern(
        meta=meta(spec, params, family_name(craft, "hat_bonnet"), "title.hat_bonnet"),
        spec=spec,
        params=params,
        sections=tuple(sections),
        measurements=fitted(measurements),
        materials=materials(
            craft,
            spec,
            params,
            area,
            (
                "notion.crochet_hook" if craft.crochet else "notion.tape_measure",
                "notion.tapestry_needle",
            ),
            extra_meters=extra,
        ),
        warnings=tuple(common_warnings(craft, params)),
        joins=(
            JoinCheck("acc.join.bonnet", (CountRef("face", "end"),), (CountRef("back", "start"),)),
        ),
        finishing=tuple(notes),
    )


def generate_hat_style(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Gorro de dos agujas o de crochet segun `estilo_gorro`."""
    style = hat_style(spec)
    if style is HatStyle.BONNET:
        return _bonnet(spec, params)
    if spec.tecnica is Technique.CROCHET or style in {HatStyle.BUCKET, HatStyle.BRIMMED}:
        return _top_down(spec, params, style)
    return _bottom_up(spec, params, style)


# ---------------------------------------------------------------------------
# Pasamontanas.
# ---------------------------------------------------------------------------

# ASUNCION (patrones publicados de pasamontanas, para 56 cm de cabeza):
# cuello 10 cm, menton 2 cm, abertura 13 x 13 cm, 3 cm sobre la abertura y la
# corona de un gorro. El cuello tiene que pasar por la cabeza: 95 % del
# contorno en elastico (100 % en crochet, que no cede).
BALACLAVA_NECK = 10.0
BALACLAVA_CHIN = 2.0
BALACLAVA_ABOVE = 3.0
FACE_WIDTH = 0.24
FACE_HEIGHT = 0.23


def generate_balaclava(spec: GarmentSpec, params: PatternParams) -> Pattern:
    craft = craft_for(spec)
    params = with_gauge(craft, params)
    gauge = resolve_gauge(params)
    spc = gauge.stitches_per_cm
    head = head_cm(params)
    wanted_cm = head * (1.0 if craft.crochet else 0.95)
    if craft.crochet:
        sectors = max(6, min(12, round(flat_rate(gauge))))
        n = nearest_multiple(wanted_cm * spc, 1, minimum=4 * sectors)
        multiple = 1
    else:
        base_multiple = craft.multiple

        def fit(s: int) -> int:
            m = math.lcm(base_multiple, s, 2)
            return nearest_multiple(wanted_cm * spc, m, minimum=2 * m)

        sectors = choose_sectors(HAT_SECTORS, fit, wanted_cm * spc, spc)
        n = fit(sectors)
        multiple = base_multiple
    face = nearest_multiple(
        scale(params, 56.0 * FACE_WIDTH) * spc, math.lcm(multiple, 2), minimum=4
    )
    neck_rows = max(2, gauge.rows_for_cm(scale(params, BALACLAVA_NECK)))
    chin_rows = max(1, gauge.rows_for_cm(scale(params, BALACLAVA_CHIN)))
    face_rows = max(2, gauge.rows_for_cm(scale(params, 56.0 * FACE_HEIGHT)))
    above_rows = max(1, gauge.rows_for_cm(scale(params, BALACLAVA_ABOVE)))
    neck_id = None if craft.crochet else "rib_1x1"
    sections: list[Section] = []
    sections.append(
        build_section(
            "neck",
            "acc.section.neck",
            "round",
            0,
            [
                cast_on_row(craft, n, round_mode=True),
                *pattern_rows(
                    craft,
                    n,
                    neck_rows,
                    round_mode=True,
                    stitch_id=neck_id,
                    note="acc.note.band_crochet" if craft.crochet else "pattern.note.cuff",
                ),
            ],
            gauge,
        )
    )
    sections.append(
        build_section(
            "head",
            "acc.section.head",
            "round",
            n,
            pattern_rows(craft, n, chin_rows, round_mode=True, note="acc.note.balaclava_start"),
            gauge,
        )
    )
    rest = n - face
    if craft.crochet:
        opening: list[Row] = [
            Row(
                (*plain(craft, rest), Op(StitchKind.SKIP, times=face)),
                "acc.note.face_open_crochet",
                (("f", str(face)), ("n", str(rest))),
            )
        ]
    else:
        stitch = get_stitch(craft.stitch_id)
        opening = [
            Row(
                (Op(StitchKind.BIND_OFF, times=face), *expand_row(stitch, rest, 1)),
                "acc.note.face_open",
                (("f", str(face)),),
            )
        ]
    opening += pattern_rows(craft, rest, face_rows - 1, round_mode=False, first=2)
    sections.append(
        build_section("face_opening", "acc.section.face_opening", "flat", n, opening, gauge)
    )
    if craft.crochet:
        close = Row(
            (*plain(craft, rest), Op(StitchKind.CH, times=face)),
            "acc.note.face_close_crochet",
            (("f", str(face)),),
        )
    else:
        close = Row(
            (
                *expand_row(get_stitch(craft.stitch_id), rest, 1, in_the_round=True),
                Op(StitchKind.CAST_ON, times=face),
            ),
            "acc.note.face_close",
            (("f", str(face)),),
        )
    top = [close, *pattern_rows(craft, n, above_rows, round_mode=True, first=2)]
    if craft.crochet:
        crown, _end = decrease_to(craft, n, sectors, sectors, note="acc.note.crown_decrease")
        top_section = build_section(
            "top", "acc.section.top", "round", rest, top + crown, gauge, gather=True
        )
    else:
        crown_rows = sector_crown(n, sectors, gauge.rows_for_cm(scale(params, 7.0)))
        top_section = build_section(
            "top", "acc.section.top", "round", rest, top + crown_rows, gauge, gather=True
        )
    sections.append(top_section)
    edge = 2 * face + 2 * pick_up(gauge, face_rows)
    edge += edge % 2
    edge_rows = max(2, gauge.rows_for_cm(2.5)) if not craft.crochet else 2
    sections.append(
        build_section(
            "face_edge",
            "acc.section.face_edge",
            "round",
            edge,
            pattern_rows(
                craft,
                edge,
                edge_rows,
                round_mode=True,
                stitch_id=None if craft.crochet else "rib_1x1",
                note="acc.note.face_edge",
            ),
            gauge,
            bind_off=True,
            meta={"picked": edge},
        )
    )
    measurements = [
        Measurement(
            key="head", value_cm=head, target_cm=head, tolerance_cm=0.1, kind="circumference"
        ),
        Measurement(
            key="circumference",
            value_cm=gauge.cm_for_stitches(n),
            target_cm=wanted_cm,
            tolerance_cm=repeat_tolerance(gauge, math.lcm(multiple, sectors, 2), 2.5),
            kind="circumference",
        ),
        Measurement(
            key="face_width",
            value_cm=gauge.cm_for_stitches(face),
            target_cm=scale(params, 56.0 * FACE_WIDTH),
            tolerance_cm=repeat_tolerance(gauge, math.lcm(multiple, 2), 1.0),
            kind="width",
        ),
        Measurement(
            key="face_height",
            value_cm=gauge.cm_for_rows(face_rows),
            target_cm=scale(params, 56.0 * FACE_HEIGHT),
            tolerance_cm=_length_tolerance(gauge, 1.0),
            kind="length",
        ),
        Measurement(
            key="neck_length",
            value_cm=gauge.cm_for_rows(neck_rows),
            target_cm=scale(params, BALACLAVA_NECK),
            tolerance_cm=_length_tolerance(gauge, 1.0),
            kind="length",
        ),
    ]
    total_rows = sum(s.meta["row_count"] for s in sections[:4])
    area = gauge.cm_for_stitches(n) * gauge.cm_for_rows(total_rows)
    return Pattern(
        meta=meta(spec, params, family_name(craft, "balaclava"), "title.balaclava"),
        spec=spec,
        params=params,
        sections=tuple(sections),
        measurements=fitted(measurements),
        materials=materials(
            craft,
            spec,
            params,
            area,
            (
                "notion.crochet_hook" if craft.crochet else "notion.stitch_markers",
                "notion.tapestry_needle",
                "notion.tape_measure",
            ),
        ),
        warnings=tuple(common_warnings(craft, params)),
        joins=(
            JoinCheck("acc.join.neck", (CountRef("neck", "end"),), (CountRef("head", "start"),)),
            JoinCheck(
                "acc.join.face", (CountRef("head", "end"),), (CountRef("face_opening", "start"),)
            ),
            JoinCheck(
                "acc.join.top", (CountRef("face_opening", "end"),), (CountRef("top", "start"),)
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Vincha / cubreorejas.
# ---------------------------------------------------------------------------

HEADBAND_WIDTH = 10.0  # ASUNCION: alto de la vincha para 56 cm de cabeza
HEADBAND_EASE = 0.9  # ASUNCION: la vincha ajusta un 10 % (como el borde del gorro)


def generate_headband(spec: GarmentSpec, params: PatternParams) -> Pattern:
    craft = craft_for(spec, knit_default="garter")
    params = with_gauge(craft, params)
    gauge = resolve_gauge(params)
    head = head_cm(params)
    width_cm = dimension(params, "width", scale(params, HEADBAND_WIDTH))
    length_cm = dimension(params, "length", head * (HEADBAND_EASE if not craft.crochet else 0.95))
    stitches = nearest_multiple(width_cm * gauge.stitches_per_cm, craft.multiple, minimum=3)
    rows = max(2, gauge.rows_for_cm(length_cm))
    section = build_section(
        "headband",
        "acc.section.headband",
        "flat",
        0,
        [
            cast_on_row(craft, stitches, round_mode=False),
            *pattern_rows(
                craft,
                stitches,
                rows,
                round_mode=False,
                note="pattern.note.crochet_flat" if craft.crochet else "acc.note.headband_rows",
            ),
        ],
        gauge,
        bind_off=True,
    )
    return Pattern(
        meta=meta(spec, params, family_name(craft, "headband"), "title.headband"),
        spec=spec,
        params=params,
        sections=(section,),
        measurements=fitted(
            [
                Measurement(
                    key="head",
                    value_cm=head,
                    target_cm=head,
                    tolerance_cm=0.1,
                    kind="circumference",
                ),
                Measurement(
                    key="width",
                    value_cm=gauge.cm_for_stitches(stitches),
                    target_cm=width_cm,
                    tolerance_cm=repeat_tolerance(gauge, craft.multiple, 1.0),
                    kind="width",
                ),
                Measurement(
                    key="length",
                    value_cm=gauge.cm_for_rows(rows),
                    target_cm=length_cm,
                    tolerance_cm=_length_tolerance(gauge),
                    kind="length",
                ),
            ]
        ),
        materials=materials(
            craft,
            spec,
            params,
            width_cm * length_cm,
            (
                "notion.crochet_hook" if craft.crochet else "notion.tape_measure",
                "notion.tapestry_needle",
            ),
        ),
        warnings=tuple(common_warnings(craft, params)),
        finishing=(
            Note("acc.finish.headband_seam", {}),
            Note("acc.finish.headband_twist", {"cm": f"{round_half_up(width_cm / 2)}"}),
        ),
    )


def generate_crochet_hat_style(spec: GarmentSpec, params: PatternParams) -> Pattern:
    return generate_hat_style(spec, params)
