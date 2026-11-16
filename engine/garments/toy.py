"""Juguetes (amigurumi) en piezas: cabeza, cuerpo, brazos, piernas y detalles.

Como un patron de juguete publicado: cada pieza se teje aparte, se rellena y
se cose. Las proporciones salen de plantillas deterministas (`TEMPLATES`) que
escalan con una sola medida, la altura total del muneco sentado; la IA solo
elige la plantilla (`GarmentSpec.figura`).

Dos tecnicas con la misma geometria:
- crochet: espiral de puntos bajos desde un anillo magico de 6 pts, con
  aumentos y disminuciones de 6 pts por vuelta (convencion amigurumi);
- dos agujas: cada pieza en plano y en jersey desde pocos puntos montados, con
  aumentos kfb y disminuciones 2pjd en las hileras del derecho; al terminar se
  fruncen los extremos y se cose el costado. Se eligio en plano (y no en
  redondo con agujas de doble punta) porque montar 6-8 pts en redondo es lo
  mas dificil para una principiante; ver DECISIONS.md.

Cada pieza crece desde su extremo cerrado; su forma es una lista de tramos
(`Seg`): contorno objetivo y largo sobre el tejido. Los conteos y la
distribucion de aumentos los calcula este modulo y el simulador los verifica.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from math import pi
from typing import Literal

from engine import ENGINE_VERSION
from engine.garments.base import ImpossibleProportionsError
from engine.gauge import DEFAULT_GAUGES, Gauge, crochet_gauge
from engine.ir import (
    Item,
    Materials,
    Measurement,
    Note,
    Op,
    Pattern,
    PatternMeta,
    Repeat,
    Section,
    SectionTarget,
    Step,
    Warning,
    build_step,
)
from engine.materials import estimate_yarn
from engine.rounding import round_half_up
from engine.spec import Figure, GarmentSpec, PatternParams, Technique, YarnWeight
from engine.stitches.kinds import StitchKind

# ---------------------------------------------------------------------------
# Convenciones (ASUNCION: ver DECISIONS.md y docs/fuentes.md).
# ---------------------------------------------------------------------------

# Altura del muneco sentado si la persona no la da: crece con el hilo para que
# las piezas chicas (cola, orejas) tengan al menos un par de vueltas.
DEFAULT_HEIGHT_CM: dict[YarnWeight, float] = {
    YarnWeight.LACE: 10.0,
    YarnWeight.FINGERING: 14.0,
    YarnWeight.SPORT: 18.0,
    YarnWeight.DK: 22.0,
    YarnWeight.WORSTED: 26.0,
    YarnWeight.BULKY: 32.0,
    YarnWeight.SUPER_BULKY: 40.0,
    YarnWeight.UNKNOWN: 22.0,
}

# Los juguetes se tejen apretados para que no se vea el relleno: ganchillo o
# agujas mas finos que los del grosor y, por eso, mas puntos por cm.
TOY_HOOK_MM: dict[YarnWeight, float] = {
    YarnWeight.LACE: 1.5,
    YarnWeight.FINGERING: 2.0,
    YarnWeight.SPORT: 2.5,
    YarnWeight.DK: 3.0,
    YarnWeight.WORSTED: 3.5,
    YarnWeight.BULKY: 5.0,
    YarnWeight.SUPER_BULKY: 7.0,
    YarnWeight.UNKNOWN: 3.0,
}
TOY_NEEDLE_MM: dict[YarnWeight, float] = {
    YarnWeight.LACE: 1.75,
    YarnWeight.FINGERING: 2.25,
    YarnWeight.SPORT: 2.75,
    YarnWeight.DK: 3.25,
    YarnWeight.WORSTED: 3.75,
    YarnWeight.BULKY: 5.0,
    YarnWeight.SUPER_BULKY: 7.0,
    YarnWeight.UNKNOWN: 3.25,
}
CROCHET_TIGHTNESS = 1.25  # pb de amigurumi vs pb de la tabla CYC
KNIT_TIGHTNESS = 1.15  # jersey de juguete vs jersey de la tabla CYC

# Aumentos por vuelta (crochet) o por hilera del derecho (agujas). En crochet
# es la convencion del amigurumi (anillo de 6 pb, +6 por vuelta). En agujas,
# 8 se acerca al circulo plano en jersey (2 pi x pts/cm / hileras/cm x 2
# hileras ~ 9) sin que el montaje inicial sea dificil.
SECTORS: dict[Literal["crochet", "knit"], int] = {"crochet": 6, "knit": 8}

SAFETY_EYES_MM = (6, 8, 9, 10, 12, 15, 18, 21, 24)

# La cabeza se hunde un poco en el cuello y el cuerpo se inclina al sentarse.
HEAD_VISIBLE = 0.9
BODY_VISIBLE = 0.9

Stuffing = Literal["firm", "light", "none"]


@dataclass(frozen=True)
class Seg:
    """Tramo de una pieza: llegar al contorno `circ` en un largo `length`.

    Ambos son fracciones de la altura total. `length=None`: lo mas rapido que
    permiten los aumentos (base plana); `length=FILL`: lo que falta para el
    largo total de la pieza, sin cambiar el conteo.
    """

    circ: float
    length: float | None


FILL = -1.0


@dataclass(frozen=True)
class PieceTemplate:
    id: str  # head, body, arm, leg, ear, muzzle, tail
    copies: int
    length: float  # largo total sobre el tejido (fraccion de la altura)
    segs: tuple[Seg, ...]
    closed: bool  # termina cerrada (se frunce) o abierta (se cose al muneco)
    stuffing: Stuffing
    variant: str = ""  # textos propios: ear_long, ear_pointy, tail_long...


def _ball(piece_id: str, diameter: float, copies: int = 1) -> PieceTemplate:
    circ = pi * diameter
    return PieceTemplate(
        piece_id, copies, pi * diameter / 2, (Seg(circ, None), Seg(circ, FILL)), True, "firm"
    )


def _tube(
    piece_id: str,
    diameter: float,
    length: float,
    *,
    copies: int = 2,
    stuffing: Stuffing = "firm",
    taper: float = 1.0,
    taper_length: float = 0.0,
    variant: str = "",
) -> PieceTemplate:
    circ = pi * diameter
    segs = [Seg(circ, None), Seg(circ, FILL)]
    if taper != 1.0:
        segs.append(Seg(circ * taper, taper_length))
    return PieceTemplate(piece_id, copies, length, tuple(segs), False, stuffing, variant)


HEAD_D = 0.52
BODY_D = 0.38
BODY_SIDE = 0.58


def _base_pieces() -> list[PieceTemplate]:
    body_circ = pi * BODY_D
    body = PieceTemplate(
        "body",
        1,
        BODY_D / 2 + BODY_SIDE,
        (Seg(body_circ, None), Seg(body_circ, FILL), Seg(body_circ * 0.62, 0.2)),
        False,
        "firm",
    )
    return [
        _ball("head", HEAD_D),
        body,
        _tube("arm", 0.12, 0.34, stuffing="light"),
        _tube("leg", 0.16, 0.28),
    ]


def _bear() -> tuple[PieceTemplate, ...]:
    return (
        *_base_pieces(),
        _tube("ear", 0.16, 0.11, stuffing="none", variant="ear_round"),
        _tube("muzzle", 0.2, 0.13, copies=1, stuffing="light"),
        _ball("tail", 0.08),
    )


def _bunny() -> tuple[PieceTemplate, ...]:
    return (
        *_base_pieces(),
        _tube(
            "ear", 0.12, 0.42, stuffing="none", taper=0.7, taper_length=0.06, variant="ear_long"
        ),
        _ball("tail", 0.12),
    )


def _cat() -> tuple[PieceTemplate, ...]:
    ear = PieceTemplate(
        "ear", 2, 0.12, (Seg(pi * 0.16, 0.12),), False, "none", "ear_pointy"
    )
    tail = _tube("tail", 0.07, 0.34, copies=1, stuffing="light", variant="tail_long")
    return (*_base_pieces(), ear, tail)


TEMPLATES: dict[Figure, tuple[PieceTemplate, ...]] = {
    Figure.BEAR: _bear(),
    Figure.BUNNY: _bunny(),
    Figure.CAT: _cat(),
    Figure.GENERIC: tuple(_base_pieces()),
}

# ---------------------------------------------------------------------------
# Geometria -> vueltas.
# ---------------------------------------------------------------------------

Craft = Literal["crochet", "knit"]


@dataclass(frozen=True)
class _Plan:
    """Conteo al final de cada unidad (vuelta de crochet o par de hileras)."""

    counts: tuple[int, ...]  # incluye el conteo inicial en [0]
    base_units: int  # unidades del primer tramo (base o punta cerrada)


def _quantize(circ_cm: float, gauge: Gauge, sectors: int) -> int:
    wanted = circ_cm * gauge.stitches_per_cm / sectors
    return max(1, round_half_up(wanted)) * sectors


def _spread(start: int, end: int, units: int, sectors: int) -> list[int]:
    """Conteos de `units` unidades que van de `start` a `end` en cambios de
    `sectors` puntos, repartidos parejo y centrados en el tramo."""
    changes = abs(end - start) // sectors
    sign = 1 if end >= start else -1
    counts: list[int] = []
    current = start

    def done(index: int) -> int:  # cambios hechos antes de la unidad `index`
        return (2 * index * changes + units) // (2 * units)

    for index in range(units):
        if done(index + 1) > done(index):
            current += sign * sectors
        counts.append(current)
    return counts


def _plan(piece: PieceTemplate, height: float, gauge: Gauge, craft: Craft) -> _Plan:
    sectors = SECTORS[craft]
    unit_rows = 1 if craft == "crochet" else 2
    rows_per_unit_cm = gauge.rows_per_cm / unit_rows
    target_rows = piece.length * height * gauge.rows_per_cm
    if craft == "knit" and piece.closed:
        target_rows += 1  # la ultima hilera del reves no se teje: se frunce
    total_units = max(1, round_half_up(target_rows / unit_rows))
    start_units = 1 if craft == "crochet" else 0  # el anillo ocupa una vuelta
    targets = [_quantize(seg.circ * height, gauge, sectors) for seg in piece.segs]
    closing = (targets[-1] - sectors) // sectors if piece.closed else 0
    fixed: list[int | None] = []
    count = sectors
    for index, (seg, target) in enumerate(zip(piece.segs, targets, strict=True)):
        needed = abs(target - count) // sectors
        if seg.length is None:
            fixed.append(needed)
        elif seg.length == FILL:
            fixed.append(None)
        else:
            spread = round_half_up(seg.length * height * rows_per_unit_cm)
            if index == 0:  # el largo del primer tramo incluye el anillo
                spread -= start_units
            fixed.append(max(needed, spread))
        count = target
    used = start_units + closing + sum(units for units in fixed if units is not None)
    fill = max(0, total_units - used)
    counts = [sectors]
    for planned, target in zip(fixed, targets, strict=True):
        counts.extend(_spread(counts[-1], target, fill if planned is None else planned, sectors))
    if piece.closed:
        counts.extend(_spread(counts[-1], sectors, closing, sectors))
    first = fixed[0] if fixed[0] is not None else fill
    return _Plan(counts=tuple(counts), base_units=first)


def _change_items(count: int, delta: int, plain: StitchKind, inc: StitchKind, dec: StitchKind) -> list[Item]:
    if delta == 0:
        return [Op(plain, times=count)]
    sectors = abs(delta)
    if delta > 0:
        gap = count // sectors - 1
        unit: tuple[Op, ...] = ((Op(plain, times=gap),) if gap else ()) + (Op(inc),)
    else:
        gap = count // sectors - 2
        unit = ((Op(plain, times=gap),) if gap else ()) + (Op(dec),)
    return [Repeat(sectors, unit)]


@dataclass(frozen=True)
class _Built:
    section: Section
    plan: _Plan
    rows: int  # vueltas o hileras totales
    area_cm2: float


_START_NOTE = {
    "head": "pattern.note.toy_start_head",
    "body": "pattern.note.toy_start_body",
    "arm": "pattern.note.toy_start_arm",
    "leg": "pattern.note.toy_start_leg",
    "tail": "pattern.note.toy_start_tail",
}


def _stuff_keys(piece: PieceTemplate) -> list[str]:
    """Relleno de las piezas abiertas; las cerradas se rellenan al cerrarlas."""
    if piece.closed:
        return []
    return [f"pattern.toy_stuff.{piece.variant or piece.id}"]


def _build_section(
    piece: PieceTemplate, height: float, gauge: Gauge, craft: Craft
) -> _Built:
    plan = _plan(piece, height, gauge, craft)
    counts = plan.counts
    steps: list[Step] = []
    # Rellenar las piezas cerradas de crochet antes de las dos ultimas
    # vueltas de cierre (despues el agujero es chico para el relleno).
    closing = (max(counts) - counts[-1]) // SECTORS[craft] if piece.closed else 0
    stuff_at = len(counts) - min(2, closing) if closing and craft == "crochet" else -1
    if craft == "crochet":
        steps.append(build_step(1, 0, (Op(StitchKind.MAGIC_RING),)))
        for index in range(1, len(counts)):
            items = _change_items(
                counts[index - 1],
                counts[index] - counts[index - 1],
                StitchKind.SC,
                StitchKind.CROCHET_INC,
                StitchKind.CROCHET_DEC,
            )
            note = "pattern.note.toy_stuff" if index == stuff_at else None
            steps.append(build_step(index + 1, counts[index - 1], items, note_key=note))
        start = 0
    else:
        number = 1
        for index in range(1, len(counts)):
            items = _change_items(
                counts[index - 1],
                counts[index] - counts[index - 1],
                StitchKind.KNIT,
                StitchKind.KFB,
                StitchKind.K2TOG,
            )
            steps.append(build_step(number, counts[index - 1], items))
            number += 1
            last = index == len(counts) - 1
            if not (last and piece.closed):  # la ultima hilera cerrada se frunce
                steps.append(build_step(number, counts[index], (Op(StitchKind.PURL, times=counts[index]),)))
                number += 1
        start = counts[0]
    rows = len(steps)
    end = counts[-1]
    target_cm = piece.length * height
    note_keys: list[str] = []
    if piece.id in _START_NOTE:
        note_keys.append(_START_NOTE[piece.id])
    if piece.id == "head":
        note_keys.append("pattern.note.toy_eyes_first")
    if craft == "knit":
        note_keys.append("pattern.note.toy_ws_purl")
    if craft == "crochet":
        end_keys = ["pattern.toy_close_crochet" if piece.closed else "pattern.toy_open_crochet"]
    else:
        end_keys = ["pattern.toy_close_knit" if piece.closed else "pattern.toy_open_knit"]
    end_keys.extend(_stuff_keys(piece))
    meta = {
        "row_count": rows,
        "toy": 1,
        "copies": piece.copies,
        "max_stitches": max(counts),
        "base_units": plan.base_units,
    }
    if craft == "knit":
        meta["cast_on_start"] = 1
        meta["ws_purl"] = 1
    section = Section(
        id=piece.id,
        name_key=f"section.toy_{piece.id}" + ("s" if piece.copies == 2 else ""),
        mode="round" if craft == "crochet" else "flat",
        steps=tuple(steps),
        start_stitches=start,
        end_stitches=end,
        target=SectionTarget(
            measurement_key=f"{piece.id}_length",
            target_cm=target_cm,
            tolerance_cm=max(1.0, 0.2 * target_cm),
            dimension="length",
        ),
        meta=meta,
        bind_off=False,
        note_keys=tuple(note_keys),
        end_note_keys=tuple(end_keys),
    )
    area = sum(step.stitch_count_end for step in steps) / gauge.stitches_per_cm / gauge.rows_per_cm
    return _Built(section, plan, rows, area * piece.copies)


# ---------------------------------------------------------------------------
# Armado (numeros calculados a partir de las vueltas reales).
# ---------------------------------------------------------------------------


def _row_of(built: _Built, fraction: float) -> int:
    return max(2, min(built.rows - 1, round_half_up(built.rows * fraction)))


def _count_at(built: _Built, row: int) -> int:
    return built.section.steps[row - 1].stitch_count_end


def _assembly(
    figure: Figure, built: dict[str, _Built], craft: Craft, head_cm: float
) -> tuple[Note, ...]:
    suffix = craft
    head, body = built["head"], built["body"]
    notes: list[Note] = []
    eye_row = _row_of(head, 0.56)
    eye_gap = max(2, round_half_up(head.section.meta["max_stitches"] * 0.18))
    eye_mm = min(SAFETY_EYES_MM, key=lambda mm: abs(mm - head_cm * 1.05))
    notes.append(
        Note(f"finishing.toy.eyes.{suffix}", {"a": eye_row, "b": eye_row + 1, "n": eye_gap, "mm": eye_mm})
    )
    if "muzzle" in built:
        notes.append(Note(f"finishing.toy.muzzle.{suffix}", {"a": eye_row + 1}))
    else:
        nose_key = "finishing.toy.nose_cat" if figure is Figure.CAT else "finishing.toy.nose"
        notes.append(Note(nose_key, {}))
    if "ear" in built:
        variant = "ear_long" if figure is Figure.BUNNY else "ear"
        row = _row_of(head, 0.12 if figure is Figure.BUNNY else 0.2)
        gap = max(2, round_half_up(_count_at(head, row) * (0.15 if figure is Figure.BUNNY else 0.3)))
        notes.append(Note(f"finishing.toy.{variant}.{suffix}", {"a": row, "b": row + 1, "n": gap}))
    neck_row = max(2, body.rows - (2 if craft == "crochet" else 4))
    notes.append(Note("finishing.toy.head_body", {}))
    notes.append(Note(f"finishing.toy.arms.{suffix}", {"a": neck_row}))
    base_row = body.plan.base_units + (1 if craft == "crochet" else 0)
    if craft == "knit":
        base_row = 2 * body.plan.base_units
    leg_gap = max(2, round_half_up(body.section.meta["max_stitches"] * 0.2))
    notes.append(Note(f"finishing.toy.legs.{suffix}", {"a": max(2, base_row), "n": leg_gap}))
    if "tail" in built:
        notes.append(Note(f"finishing.toy.tail.{suffix}", {"a": max(2, base_row + 2)}))
    return tuple(notes)


# ---------------------------------------------------------------------------
# Generador.
# ---------------------------------------------------------------------------


def _toy_params(params: PatternParams, craft: Craft) -> PatternParams:
    if params.densidad is not None:
        return params
    if craft == "crochet":
        base = crochet_gauge(params.peso_hilo.value, "crochet_sc")
        factor = CROCHET_TIGHTNESS
    else:
        base = DEFAULT_GAUGES.get(params.peso_hilo.value, DEFAULT_GAUGES["dk"])
        factor = KNIT_TIGHTNESS
    gauge = Gauge(
        stitches_per_10cm=round(base.stitches_per_10cm * factor, 1),
        rows_per_10cm=round(base.rows_per_10cm * factor, 1),
    )
    return params.model_copy(update={"densidad": gauge})


def toy_height(params: PatternParams) -> float:
    return params.dimensiones_cm.get(
        "height", params.medidas_cm.get("height", DEFAULT_HEIGHT_CM[params.peso_hilo])
    )


def generate_amigurumi(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Juguete en piezas (crochet o dos agujas) segun la plantilla de la figura."""
    if spec.tecnica is Technique.CROCHET:
        craft: Craft = "crochet"
    elif spec.tecnica in {Technique.NEEDLES, Technique.CIRCULAR}:
        craft = "knit"
    else:
        raise ImpossibleProportionsError("error.unsupported_technique", technique=spec.tecnica.value)
    figure = spec.figura or Figure.GENERIC
    params = _toy_params(params, craft)
    gauge = params.densidad
    assert gauge is not None
    height = toy_height(params)
    pieces = TEMPLATES[figure]
    built = {piece.id: _build_section(piece, height, gauge, craft) for piece in pieces}
    head, body = built["head"], built["body"]
    sectors = SECTORS[craft]
    if head.section.meta["max_stitches"] < 4 * sectors:
        raise ImpossibleProportionsError(
            "error.too_small_for_yarn", weight=params.peso_hilo.value, target=round(height, 1)
        )
    for item in built.values():
        section = item.section
        assert section.target is not None
        actual = gauge.cm_for_rows(item.rows)
        if abs(actual - section.target.target_cm) > section.target.tolerance_cm:
            raise ImpossibleProportionsError(
                "error.too_small_for_yarn", weight=params.peso_hilo.value, target=round(height, 1)
            )
    head_d = 2 * gauge.cm_for_rows(head.rows) / pi
    base_cm = gauge.cm_for_rows(body.plan.base_units * (1 if craft == "crochet" else 2))
    body_side = gauge.cm_for_rows(body.rows) - base_cm
    height_actual = HEAD_VISIBLE * head_d + BODY_VISIBLE * body_side
    head_circ = gauge.cm_for_stitches(head.section.meta["max_stitches"])
    body_circ = gauge.cm_for_stitches(body.section.meta["max_stitches"])
    measurements = (
        Measurement(
            key="toy_height",
            value_cm=height_actual,
            target_cm=height,
            tolerance_cm=max(1.5, 0.12 * height),
            kind="length",
        ),
        Measurement(
            key="toy_head",
            value_cm=head_circ,
            target_cm=pi * HEAD_D * height,
            tolerance_cm=max(1.5, 0.15 * pi * HEAD_D * height),
            kind="circumference",
        ),
        Measurement(
            key="toy_body",
            value_cm=body_circ,
            target_cm=pi * BODY_D * height,
            tolerance_cm=max(1.5, 0.15 * pi * BODY_D * height),
            kind="circumference",
        ),
    )
    area = sum(item.area_cm2 for item in built.values())
    meters, grams = estimate_yarn(area, params.peso_hilo)
    if craft == "crochet":
        hook: float | None = params.ganchillo_mm or TOY_HOOK_MM[params.peso_hilo]
        needle: float | None = None
        tools: tuple[str, ...] = ("notion.stitch_markers",)
    else:
        hook = None
        needle = params.aguja_mm or TOY_NEEDLE_MM[params.peso_hilo]
        tools = ()
    notions = (
        *tools,
        "notion.toy_stuffing",
        "notion.safety_eyes",
        "notion.embroidery_yarn",
        "notion.tapestry_needle",
        "notion.pins",
    )
    materials = Materials(
        yarn_weight=params.peso_hilo,
        needle_mm=needle,
        hook_mm=hook,
        meters=meters,
        grams=grams,
        notions=notions,
        colors=tuple(spec.colorwork.paleta) if spec.colorwork else (),
    )
    warnings = [
        Warning(f"toy_construction_{craft}", f"warning.toy_construction.{craft}", severity="info"),
        Warning("toy_tight", f"warning.toy_tight.{craft}", severity="info"),
        Warning("toy_safety", "warning.toy_safety", severity="warning"),
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", "warning.toy_proportions", severity="info"),
    ]
    if spec.figura is None:
        warnings.append(Warning("toy_generic", "warning.toy_generic", severity="info"))
    digest = hashlib.sha256(
        (spec.model_dump_json() + params.model_dump_json() + "amigurumi").encode("utf-8")
    ).hexdigest()[:12]
    meta = PatternMeta(
        id=digest,
        family="amigurumi",
        title_key=f"title.toy_{figure.value}",
        size=params.talla,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        engine_version=ENGINE_VERSION,
    )
    return Pattern(
        meta=meta,
        spec=spec,
        params=params,
        sections=tuple(item.section for item in built.values()),
        measurements=measurements,
        materials=materials,
        warnings=tuple(warnings),
        finishing=_assembly(figure, built, craft, head_d),
    )
