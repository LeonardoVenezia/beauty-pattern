"""Juguetes (amigurumi): formas de cuerpo x figuras x partes, crochet y agujas.

Como un patron de juguete publicado: cada pieza se teje aparte, se rellena y
se cose. Tres capas de datos deterministas, todas en tablas de este modulo:

- **Forma de cuerpo** (`ToyBody`, `PLANS`): las piezas grandes y su geometria
  (en piezas sentado, bolita, de una pieza con cuello, de pie en dos o en
  cuatro patas, alargado con patas o sin patas, radial con tentaculos).
- **Kit de partes** (`PARTS`): orejas, hocicos, colas, alas, cuernos, antenas,
  caparazon, puas... cada una con su forma y su tamano relativo a la cabeza.
- **Figura** (`FIGURES`): forma de cuerpo por defecto, formas que admite,
  partes con su factor de tamano y detalles bordados o anudados (melena,
  pelo, lana, rayas).

La IA solo elige la figura y la forma (`GarmentSpec.figura`,
`GarmentSpec.cuerpo_juguete`). Todo numero sale de aca: conteos, vueltas y
la posicion de cada parte en el armado, calculada sobre las vueltas reales.

Dos tecnicas con la misma geometria:
- crochet: espiral de puntos bajos desde un anillo magico de 6 pts, con
  aumentos y disminuciones de 6 pts por vuelta (convencion amigurumi);
- dos agujas: cada pieza en plano y en jersey desde pocos puntos montados, con
  aumentos kfb y disminuciones 2pjd en las hileras del derecho; al terminar se
  fruncen los extremos y se cose el costado (ver DECISIONS D033).

Cada pieza crece desde su extremo cerrado; su forma es una lista de tramos
(`Seg`): contorno objetivo y largo sobre el tejido. Los conteos y la
distribucion de aumentos los calcula este modulo y el simulador los verifica.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
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
from engine.spec import Figure, GarmentSpec, PatternParams, Technique, ToyBody, YarnWeight
from engine.stitches.kinds import StitchKind

# ---------------------------------------------------------------------------
# Convenciones (ASUNCION: ver DECISIONS.md D033, D036 y la entrada de formas y kit de partes).
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
# Al rellenar, el casquete que se cierra con disminuciones planas sube como
# una cupula: ~0,6 de su largo sobre el tejido.
DOME_RISE = 0.6

Stuffing = Literal["firm", "light", "none"]
Craft = Literal["crochet", "knit"]


@dataclass(frozen=True)
class Seg:
    """Tramo de una pieza: llegar al contorno `circ` en un largo `length`.

    Ambos son fracciones de la altura total. `length=None`: lo mas rapido que
    permiten los aumentos (base plana); `length=FILL`: lo que falta para el
    largo total de la pieza, sin cambiar el conteo. `rise`: cuanto de su
    largo sobre el tejido suma a la altura del muneco armado.
    """

    circ: float
    length: float | None
    rise: float = 1.0


FILL = -1.0


@dataclass(frozen=True)
class PieceTemplate:
    id: str  # head, body, arm, leg, ear, muzzle, tail...
    copies: int
    length: float  # largo total sobre el tejido (fraccion de la altura)
    segs: tuple[Seg, ...]
    closed: bool  # termina cerrada (se frunce) o abierta (se cose al muneco)
    stuffing: Stuffing
    variant: str = ""  # textos propios: ear_long, ear_pointy, tail_long...
    name: str = ""  # nombre de la seccion si no es id (+ "s" si hay copias)
    stripes: bool = False  # rayas de color en el tramo del cuerpo (abeja)

    @property
    def name_key(self) -> str:
        return "section.toy_" + (self.name or self.id + ("s" if self.copies > 1 else ""))


def _ball(piece_id: str, diameter: float, copies: int = 1, variant: str = "") -> PieceTemplate:
    circ = pi * diameter
    return PieceTemplate(
        piece_id,
        copies,
        pi * diameter / 2,
        (Seg(circ, None, 0.0), Seg(circ, FILL)),
        True,
        "firm",
        variant,
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
    name: str = "",
) -> PieceTemplate:
    circ = pi * diameter
    segs = [Seg(circ, None, 0.0), Seg(circ, FILL)]
    if taper != 1.0:
        segs.append(Seg(circ * taper, taper_length))
    return PieceTemplate(piece_id, copies, length, tuple(segs), False, stuffing, variant, name)


def _cone(
    piece_id: str,
    diameter: float,
    length: float,
    *,
    copies: int = 1,
    stuffing: Stuffing = "firm",
    variant: str = "",
    name: str = "",
) -> PieceTemplate:
    return PieceTemplate(
        piece_id, copies, length, (Seg(pi * diameter, length),), False, stuffing, variant, name
    )


# ---------------------------------------------------------------------------
# Kit de partes. Medidas en "unidades de muneco sentado": fracciones de la
# altura del muneco en piezas, cuya cabeza mide HEAD_D. Cada forma de cuerpo
# las escala con `Plan.scale` (su cabeza / HEAD_D) y cada figura con su
# factor. ASUNCION: tamanos medidos a ojo sobre amigurumis publicados.
# ---------------------------------------------------------------------------

HEAD_D = 0.52
BODY_D = 0.38
BODY_SIDE = 0.58

Shape = Literal["tube", "cone", "ball"]


@dataclass(frozen=True)
class PartShape:
    id: str
    shape: Shape
    d: float
    length: float
    copies: int = 2
    stuffing: Stuffing = "none"
    taper: float = 1.0
    taper_length: float = 0.0
    name: str = ""


PARTS: dict[str, PartShape] = {
    # Orejas.
    "ear_round": PartShape("ear", "tube", 0.16, 0.11),
    "ear_pointy": PartShape("ear", "cone", 0.16, 0.12),
    "ear_long": PartShape("ear", "tube", 0.12, 0.42, taper=0.7, taper_length=0.06),
    "ear_floppy": PartShape("ear", "tube", 0.14, 0.24, taper=0.75, taper_length=0.06),
    "ear_flat": PartShape("ear", "tube", 0.30, 0.18),
    "ear_cup": PartShape("ear", "tube", 0.12, 0.07),
    # Hocicos.
    "muzzle": PartShape("muzzle", "tube", 0.2, 0.13, copies=1, stuffing="light"),
    "muzzle_pig": PartShape("muzzle", "tube", 0.2, 0.12, copies=1, stuffing="light"),
    "muzzle_cow": PartShape("muzzle", "tube", 0.26, 0.16, copies=1, stuffing="light"),
    "trunk": PartShape(
        "trunk", "tube", 0.09, 0.32, copies=1, stuffing="light", taper=1.8, taper_length=0.1
    ),
    "beak": PartShape("beak", "cone", 0.14, 0.09, copies=1, stuffing="light"),
    # Colas.
    "tail_pompom": PartShape("tail", "ball", 0.08, 0.0, copies=1, stuffing="firm"),
    "tail_long": PartShape("tail", "tube", 0.07, 0.34, copies=1, stuffing="light"),
    "tail_stub": PartShape("tail", "tube", 0.08, 0.13, copies=1, stuffing="light"),
    "tail_curly": PartShape("tail", "tube", 0.05, 0.26, copies=1),
    "tail_cone": PartShape("tail", "cone", 0.16, 0.30, copies=1, stuffing="firm"),
    "fluke": PartShape("fluke", "tube", 0.14, 0.12),
    # Alas y aletas (dos capas: se tejen en redondo y se aplanan).
    "wing": PartShape("wing", "tube", 0.16, 0.22, taper=0.6, taper_length=0.08),
    "fin": PartShape("fin", "tube", 0.12, 0.16, taper=0.6, taper_length=0.05),
    # Cuernos, antenas, puas, ojos saltones.
    "horn_spiral": PartShape("horn", "cone", 0.10, 0.18, copies=1, stuffing="firm"),
    "horn_cow": PartShape("horn", "cone", 0.07, 0.07, stuffing="firm"),
    "antenna": PartShape("antenna", "tube", 0.05, 0.14),
    "spine": PartShape("spine", "cone", 0.09, 0.07, copies=5, stuffing="light"),
    "eyebump": PartShape("eyebump", "ball", 0.15, 0.0, stuffing="firm"),
}



def _part(kind: str, size: float) -> PieceTemplate:
    """Pieza de una parte del kit escalada por `size` (forma x figura)."""
    shape = PARTS[kind]
    variant = "" if kind == "muzzle" else kind
    if shape.shape == "ball":
        return _ball(shape.id, shape.d * size, shape.copies, variant)
    if shape.shape == "cone":
        return _cone(
            shape.id,
            shape.d * size,
            shape.length * size,
            copies=shape.copies,
            stuffing=shape.stuffing,
            variant=variant,
            name=shape.name,
        )
    return _tube(
        shape.id,
        shape.d * size,
        shape.length * size,
        copies=shape.copies,
        stuffing=shape.stuffing,
        taper=shape.taper,
        taper_length=shape.taper_length * size,
        variant=variant,
        name=shape.name,
    )


# ---------------------------------------------------------------------------
# Figuras.
# ---------------------------------------------------------------------------

Hair = Literal["mane", "doll", "unicorn", "fleece"]
Face = Literal["nose", "nose_cat", "mouth", "mouth_frog", "none"]
Long = Literal["legs", "tube", "segments"]

_SITTING = frozenset({ToyBody.PIECES, ToyBody.SEAMLESS, ToyBody.BALL, ToyBody.STANDING})


@dataclass(frozen=True)
class FigureKit:
    default: ToyBody
    bodies: frozenset[ToyBody]
    parts: tuple[tuple[str, float], ...] = ()  # (parte del kit, factor de tamano)
    quadruped: bool = False  # de pie: en cuatro patas (si no, en dos)
    face: Face = "nose"  # bordado de la cara
    hair: Hair | None = None
    stripes: bool = False
    long: Long = "legs"  # alargado: con patas (salchicha) o tubo (serpiente)
    long_d: tuple[float, float] = (0.12, 0.17)  # tubo alargado: cuerpo, cabeza
    leg_scale: float = 1.0


FIGURES: dict[Figure, FigureKit] = {
    Figure.BEAR: FigureKit(
        ToyBody.PIECES, _SITTING, (("ear_round", 1.0), ("muzzle", 1.0), ("tail_pompom", 1.0))
    ),
    Figure.BUNNY: FigureKit(ToyBody.PIECES, _SITTING, (("ear_long", 1.0), ("tail_pompom", 1.5))),
    Figure.CAT: FigureKit(
        ToyBody.PIECES,
        _SITTING | {ToyBody.LONG},
        (("ear_pointy", 1.0), ("tail_long", 1.0)),
        quadruped=True,
        face="nose_cat",
    ),
    Figure.DOG: FigureKit(
        ToyBody.PIECES,
        _SITTING | {ToyBody.LONG},
        (("ear_floppy", 1.0), ("muzzle", 1.0), ("tail_long", 0.7)),
        quadruped=True,
    ),
    Figure.ELEPHANT: FigureKit(
        ToyBody.PIECES,
        _SITTING,
        (("ear_flat", 1.0), ("trunk", 1.0), ("tail_long", 0.6)),
        quadruped=True,
        face="none",
    ),
    Figure.OCTOPUS: FigureKit(ToyBody.RADIAL, frozenset({ToyBody.RADIAL}), face="mouth"),
    Figure.DINOSAUR: FigureKit(
        ToyBody.PIECES,
        _SITTING | {ToyBody.LONG},
        (("muzzle", 0.8), ("tail_cone", 1.0), ("spine", 1.0)),
        quadruped=True,
    ),
    Figure.UNICORN: FigureKit(
        ToyBody.PIECES,
        _SITTING,
        (("ear_pointy", 0.8), ("horn_spiral", 1.0), ("muzzle_cow", 0.8)),
        quadruped=True,
        face="none",
        hair="unicorn",
    ),
    Figure.WHALE: FigureKit(
        ToyBody.BALL,
        frozenset({ToyBody.BALL, ToyBody.LONG}),
        (("fin", 1.0), ("fluke", 1.0)),
        face="mouth",
        long="tube",
        long_d=(0.30, 0.32),
    ),
    Figure.TURTLE: FigureKit(
        ToyBody.STANDING,
        frozenset({ToyBody.STANDING, ToyBody.BALL}),
        (("tail_cone", 0.4),),
        quadruped=True,
        face="mouth",
        leg_scale=0.6,
    ),
    Figure.DUCK: FigureKit(ToyBody.BALL, _SITTING, (("beak", 1.0), ("wing", 1.0)), face="none"),
    Figure.FROG: FigureKit(ToyBody.PIECES, _SITTING, (("eyebump", 1.0),), face="mouth_frog"),
    Figure.BEE: FigureKit(
        ToyBody.BALL,
        _SITTING | {ToyBody.LONG},
        (("antenna", 1.0), ("wing", 0.9)),
        face="mouth",
        stripes=True,
        long="segments",
        long_d=(0.15, 0.18),
    ),
    Figure.COW: FigureKit(
        ToyBody.PIECES,
        _SITTING,
        (("ear_cup", 1.0), ("horn_cow", 1.0), ("muzzle_cow", 1.0), ("tail_long", 0.8)),
        quadruped=True,
        face="none",
    ),
    Figure.SHEEP: FigureKit(
        ToyBody.PIECES,
        _SITTING,
        (("ear_floppy", 0.7), ("tail_pompom", 1.2)),
        quadruped=True,
        hair="fleece",
    ),
    Figure.MOUSE: FigureKit(
        ToyBody.PIECES, _SITTING, (("ear_round", 1.6), ("tail_long", 1.1)), face="nose_cat"
    ),
    Figure.FOX: FigureKit(
        ToyBody.PIECES,
        _SITTING,
        (("ear_pointy", 1.3), ("muzzle", 0.8), ("tail_cone", 1.0)),
        quadruped=True,
    ),
    Figure.OWL: FigureKit(
        ToyBody.BALL, _SITTING, (("ear_pointy", 0.5), ("beak", 0.6), ("wing", 1.0)), face="none"
    ),
    Figure.PENGUIN: FigureKit(ToyBody.BALL, _SITTING, (("beak", 0.7), ("fin", 1.0)), face="none"),
    Figure.PIG: FigureKit(
        ToyBody.PIECES,
        _SITTING,
        (("ear_pointy", 0.8), ("muzzle_pig", 1.0), ("tail_curly", 1.0)),
        quadruped=True,
        face="none",
    ),
    Figure.LION: FigureKit(
        ToyBody.PIECES,
        _SITTING,
        (("ear_round", 0.7), ("muzzle", 1.0), ("tail_long", 1.0)),
        quadruped=True,
        hair="mane",
    ),
    Figure.DOLL: FigureKit(
        ToyBody.STANDING,
        frozenset({ToyBody.STANDING, ToyBody.PIECES, ToyBody.SEAMLESS}),
        face="mouth",
        hair="doll",
    ),
    Figure.GENERIC: FigureKit(ToyBody.PIECES, frozenset(ToyBody), long="tube"),
}


def resolve_body(figure: Figure, requested: ToyBody | None) -> tuple[ToyBody, bool]:
    """(forma que se teje, si se cambio la pedida porque no tiene sentido)."""
    kit = FIGURES[figure]
    if requested is None:
        return kit.default, False
    if requested in kit.bodies:
        return requested, False
    return kit.default, True


# ---------------------------------------------------------------------------
# Formas de cuerpo: piezas grandes, en fracciones del tamano del juguete.
# ---------------------------------------------------------------------------

PlanName = Literal["pieces", "ball", "seamless", "biped", "quadruped", "dachshund", "snake", "radial"]

# Tamano por defecto de cada forma respecto del muneco sentado del mismo hilo
# (ASUNCION): la bolita mide la mitad (D036), de pie es un poco mas alto, el
# alargado se mide de punta a punta.
PLAN_SIZE: dict[PlanName, float] = {
    "pieces": 1.0,
    "ball": 0.5,
    "seamless": 1.0,
    "biped": 1.15,
    "quadruped": 1.0,
    "dachshund": 1.4,
    "snake": 1.5,
    "radial": 1.0,
}

# Proporciones de cada forma (ASUNCION, a ojo sobre patrones publicados).
# d = diametro, len = largo sobre el tejido, en fracciones del tamano.
PROPORTIONS: dict[PlanName, dict[str, float]] = {
    "pieces": {"head": HEAD_D, "body": BODY_D, "side": BODY_SIDE, "neck": 0.62},
    "ball": {"ball": 0.9, "foot_d": 0.15, "foot_len": 0.08, "scale": 1.25},
    "seamless": {
        "body": 0.40, "side": 0.536, "neck": 0.6, "neck_len": 0.10,
        "head": 0.46, "widen_len": 0.10, "head_len": 0.12,
    },
    "biped": {
        "head": 0.32, "body": 0.26, "body_len": 0.46, "neck": 0.62,
        "leg_d": 0.11, "leg_len": 0.44, "arm_d": 0.09, "arm_len": 0.36,
    },
    "quadruped": {"head": 0.48, "body": 0.44, "body_len": 0.80, "leg_d": 0.16, "leg_len": 0.38},
    "dachshund": {"head": 0.30, "body": 0.26, "body_len": 0.85, "leg_d": 0.11, "leg_len": 0.14},
    "snake": {"taper_len": 0.40, "widen_len": 0.04, "head_len": 0.06},
    "radial": {"dome": 0.50, "tentacle_d": 0.07, "tentacle_len": 0.62, "tentacle_base": 1.3},
}
# Oruga: tramos angostos entre segmentos (fraccion del contorno) y cantidad.
SEGMENT_NECK = 0.72
SEGMENTS = 4
TENTACLES = 8


def _plan_name(body: ToyBody, kit: FigureKit) -> PlanName:
    if body is ToyBody.STANDING:
        return "quadruped" if kit.quadruped else "biped"
    if body is ToyBody.LONG:
        return "dachshund" if kit.long == "legs" else "snake"
    names: dict[ToyBody, PlanName] = {
        ToyBody.PIECES: "pieces",
        ToyBody.BALL: "ball",
        ToyBody.SEAMLESS: "seamless",
        ToyBody.RADIAL: "radial",
    }
    return names[body]


def _sitting_body(d: float, side: float, neck: float) -> PieceTemplate:
    circ = pi * d
    return PieceTemplate(
        "body",
        1,
        d / 2 + side,
        (Seg(circ, None, 0.0), Seg(circ, FILL), Seg(circ * neck, 0.2)),
        False,
        "firm",
    )


def _capsule(piece_id: str, d: float, length: float, stripes: bool = False) -> PieceTemplate:
    """Cuerpo horizontal cerrado en los dos extremos (cuadrupedo)."""
    circ = pi * d
    return PieceTemplate(
        piece_id, 1, length, (Seg(circ, None, 0.0), Seg(circ, FILL)), True, "firm", stripes=stripes
    )


def _main_pieces(plan: PlanName, kit: FigureKit) -> tuple[list[PieceTemplate], float]:
    """Piezas grandes de la forma y escala de las partes del kit."""
    p = PROPORTIONS[plan]
    stripes = kit.stripes
    if plan == "pieces":
        body = _sitting_body(p["body"], p["side"], p["neck"])
        return [
            _ball("head", p["head"]),
            replace(body, stripes=stripes),
            _tube("arm", 0.12, 0.34, stuffing="light"),
            _tube("leg", 0.16, 0.28),
        ], 1.0
    if plan == "ball":
        ball = _ball("ball", p["ball"])
        return [
            replace(ball, stripes=stripes),
            _tube("foot", p["foot_d"], p["foot_len"], copies=4, stuffing="light", variant="foot"),
        ], p["scale"]
    if plan == "seamless":
        body_c, head_c = pi * p["body"], pi * p["head"]
        one = (
            Seg(body_c, None, 0.0),
            Seg(body_c, FILL),
            Seg(body_c * p["neck"], p["neck_len"]),
            Seg(head_c, p["widen_len"]),
            Seg(head_c, p["head_len"]),
        )
        length = p["body"] / 2 + p["side"] + p["neck_len"] + p["widen_len"] + p["head_len"] + p["head"] / 2
        return [
            PieceTemplate("head_body", 1, length, one, True, "firm", stripes=stripes),
            _tube("arm", 0.12 * 0.9, 0.34 * 0.9, stuffing="light"),
            _tube("leg", 0.16 * 0.9, 0.28 * 0.9),
        ], p["head"] / HEAD_D
    if plan == "biped":
        body = _sitting_body(p["body"], p["body_len"] - p["body"] / 2, p["neck"])
        return [
            _ball("head", p["head"]),
            replace(body, stripes=stripes),
            _tube("arm", p["arm_d"], p["arm_len"], stuffing="light"),
            _tube("leg", p["leg_d"], p["leg_len"]),
        ], p["head"] / HEAD_D
    if plan in {"quadruped", "dachshund"}:
        leg_len = p["leg_len"] * kit.leg_scale
        leg_d = p["leg_d"] * max(kit.leg_scale, 0.8)
        k = 1.0
        if plan == "quadruped":  # patas cortas (tortuga): el resto crece y el alto se mantiene
            nominal = 0.9 * (leg_len - leg_d / 2) + p["body"] + 0.55 * p["head"]
            reference = 0.9 * (p["leg_len"] - p["leg_d"] / 2) + p["body"] + 0.55 * p["head"]
            k = reference / nominal
        return [
            _ball("head", p["head"] * k),
            _capsule("body", p["body"] * k, p["body_len"] * k, stripes),
            _tube("leg", leg_d * k, leg_len * k, copies=4, name="legs4"),
        ], p["head"] * k / HEAD_D
    if plan == "snake":
        body_d, head_d = kit.long_d
        body_c, head_c = pi * body_d, pi * head_d
        if kit.long == "segments":
            segs: list[Seg] = [Seg(body_c, None, 0.0), Seg(body_c, FILL)]
            for _ in range(SEGMENTS):
                segs += [Seg(body_c * SEGMENT_NECK, 0.05), Seg(body_c, 0.05), Seg(body_c, 0.05)]
            segs += [Seg(head_c, p["widen_len"]), Seg(head_c, p["head_len"] * 2)]
        else:
            segs = [
                Seg(body_c, p["taper_len"]),
                Seg(body_c, FILL),
                Seg(head_c, p["widen_len"]),
                Seg(head_c, p["head_len"]),
            ]
        length = 1.0 + (1 - DOME_RISE) * head_d / 2
        return [PieceTemplate("long", 1, length, tuple(segs), True, "firm", stripes=stripes)], head_d / HEAD_D
    # radial: cupula cerrada (cabeza y cuerpo) + tentaculos.
    t_c = pi * p["tentacle_d"]
    tentacle = PieceTemplate(
        "tentacle",
        TENTACLES,
        p["tentacle_len"],
        (Seg(t_c, None, 0.0), Seg(t_c, FILL), Seg(t_c * p["tentacle_base"], 0.1)),
        False,
        "light",
        "tentacle",
    )
    return [_ball("dome", p["dome"]), tentacle], p["dome"] / HEAD_D


def _shell(body: PieceTemplate, plan: PlanName) -> PieceTemplate:
    """Caparazon de tortuga: cupula abierta del contorno del cuerpo."""
    circ = max(seg.circ for seg in body.segs) * (1.05 if plan == "ball" else 1.15)
    d = circ / pi
    depth = d * (0.5 if plan == "ball" else 0.35)
    return PieceTemplate(
        "shell", 1, d / 2 + depth, (Seg(circ, None, 0.0), Seg(circ, FILL)), False, "none", "shell"
    )


# Cambios de partes segun la forma (ASUNCION): en la bolita la cola larga se
# acorta; en el tubo alargado no hay alas (las aletas si).
PLAN_PART_SWAP: dict[PlanName, dict[str, str | None]] = {
    "ball": {"tail_long": "tail_stub", "tail_cone": "tail_stub"},
    "snake": {"wing": None, "tail_long": None, "tail_cone": None},
}


def toy_pieces(figure: Figure, body: ToyBody) -> tuple[PieceTemplate, ...]:
    """Piezas tejidas de la figura con esa forma (sin la falda radial)."""
    kit = FIGURES[figure]
    plan = _plan_name(body, kit)
    main, scale = _main_pieces(plan, kit)
    pieces = list(main)
    swap = PLAN_PART_SWAP.get(plan, {})
    for kind, factor in kit.parts:
        chosen = swap.get(kind, kind)
        if chosen is None:
            continue
        pieces.append(_part(chosen, scale * factor))
    if figure is Figure.TURTLE:
        pieces.append(_shell(main[0] if plan == "ball" else main[1], plan))
    return tuple(pieces)


def toy_plan(figure: Figure, body: ToyBody) -> PlanName:
    return _plan_name(body, FIGURES[figure])


def pattern_plan(pattern: Pattern) -> tuple[Figure, PlanName]:
    """Figura y forma con que se tejio un patron de juguete."""
    figure = pattern.spec.figura or Figure.GENERIC
    body, _ = resolve_body(figure, pattern.spec.cuerpo_juguete)
    return figure, toy_plan(figure, body)


def toy_description_keys(pattern: Pattern) -> tuple[str, str]:
    """Descripcion: una frase de la forma y otra de los detalles de la figura."""
    figure, plan = pattern_plan(pattern)
    return f"desc.toy_plan.{plan}", f"desc.toy_fig.{figure.value}"


# Compatibilidad: plantillas sentadas (en piezas) de cada figura.
TEMPLATES: dict[Figure, tuple[PieceTemplate, ...]] = {
    figure: toy_pieces(figure, ToyBody.PIECES)
    for figure in Figure
    if ToyBody.PIECES in FIGURES[figure].bodies
}

# ---------------------------------------------------------------------------
# Geometria -> vueltas.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Plan:
    """Conteo al final de cada unidad (vuelta de crochet o par de hileras)."""

    counts: tuple[int, ...]  # incluye el conteo inicial en [0]
    base_units: int  # unidades del primer tramo (base o punta cerrada)
    seg_units: tuple[int, ...] = ()  # unidades de cada tramo
    closing_units: int = 0


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
    seg_units: list[int] = []
    for planned, target in zip(fixed, targets, strict=True):
        units = fill if planned is None else planned
        seg_units.append(units)
        counts.extend(_spread(counts[-1], target, units, sectors))
    if piece.closed:
        counts.extend(_spread(counts[-1], sectors, closing, sectors))
    return _Plan(
        counts=tuple(counts), base_units=seg_units[0], seg_units=tuple(seg_units), closing_units=closing
    )


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
    piece: PieceTemplate | None = None  # None: la falda (sale de otra pieza)

    def row_of_unit(self, unit: int, craft: Craft) -> int:
        """Vuelta o hilera (del derecho) donde termina la unidad `unit`."""
        row = unit + 1 if craft == "crochet" else 2 * unit - 1
        return max(1, min(self.rows, row))

    def seg_end_row(self, index: int, craft: Craft) -> int:
        return self.row_of_unit(sum(self.plan.seg_units[: index + 1]), craft)

    def count_at(self, row: int) -> int:
        return self.section.steps[max(1, min(self.rows, row)) - 1].stitch_count_end


_START_NOTE = {
    "head": "pattern.note.toy_start_head",
    "body": "pattern.note.toy_start_body",
    "arm": "pattern.note.toy_start_arm",
    "leg": "pattern.note.toy_start_leg",
    "tail": "pattern.note.toy_start_tail",
    "ball": "pattern.note.toy_start_ball",
    "trunk": "pattern.note.toy_start_tail",
    "beak": "pattern.note.toy_start_tail",
    "horn": "pattern.note.toy_start_tail",
    "spine": "pattern.note.toy_start_tail",
    "antenna": "pattern.note.toy_start_tail",
    "tentacle": "pattern.note.toy_start_tail",
    "head_body": "pattern.note.toy_start_head_body",
    "long": "pattern.note.toy_start_long",
    "dome": "pattern.note.toy_start_dome",
    "shell": "pattern.note.toy_start_shell",
}
_FACE_PIECES = frozenset({"head", "ball", "head_body", "long", "dome"})


def _stuff_keys(piece: PieceTemplate) -> list[str]:
    """Relleno de las piezas abiertas; las cerradas se rellenan al cerrarlas."""
    if piece.closed:
        return []
    return [f"pattern.toy_stuff.{piece.variant or piece.id}"]


def _stripe_rows(counts: tuple[int, ...], plan: _Plan, craft: Craft) -> set[int]:
    """Indices de unidad (en `counts`) donde se cambia de color: franjas
    parejas en el tramo recto, cada `band` unidades."""
    start = 1 + plan.seg_units[0]
    end = len(counts) - 1 - plan.closing_units
    span = end - start
    if span < 4:
        return set()
    band = max(2, round_half_up(span / 6))
    return {start + band * k for k in range(1, span // band + 1) if start + band * k < end}


def _build_section(
    piece: PieceTemplate, height: float, gauge: Gauge, craft: Craft, dome_back_loop: bool = False
) -> _Built:
    plan = _plan(piece, height, gauge, craft)
    counts = plan.counts
    steps: list[Step] = []
    # Rellenar las piezas cerradas de crochet antes de las dos ultimas
    # vueltas de cierre (despues el agujero es chico para el relleno).
    closing = plan.closing_units if piece.closed else 0
    stuff_at = len(counts) - min(2, closing) if closing and craft == "crochet" else -1
    stripes = _stripe_rows(counts, plan, craft) if piece.stripes else set()
    # Radial: la ultima vuelta recta se teje por la hebra de atras; la falda
    # sale de las hebras delanteras que quedan libres.
    skirt_at = len(counts) - 1 - closing if dome_back_loop else -1

    def note_for(index: int) -> str | None:
        if index == stuff_at:
            return "pattern.note.toy_stuff"
        if index == skirt_at:
            return "pattern.note.toy_skirt_loops." + craft
        if index in stripes:
            return "pattern.note.toy_stripe"
        return None

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
            steps.append(build_step(index + 1, counts[index - 1], items, note_key=note_for(index)))
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
            steps.append(build_step(number, counts[index - 1], items, note_key=note_for(index)))
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
    if piece.id in _FACE_PIECES:
        note_keys.append("pattern.note.toy_eyes_first")
    if piece.stripes and stripes:
        note_keys.append("pattern.note.toy_stripes")
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
    # Las piezas chicas no pueden medir menos que su base: la tolerancia
    # admite dos vueltas (o hileras) de diferencia ademas del 20 %.
    row_cm = 1 / gauge.rows_per_cm
    section = Section(
        id=piece.id,
        name_key=piece.name_key,
        mode="round" if craft == "crochet" else "flat",
        steps=tuple(steps),
        start_stitches=start,
        end_stitches=end,
        target=SectionTarget(
            measurement_key=f"{piece.id}_length",
            target_cm=target_cm,
            tolerance_cm=max(1.0, 0.2 * target_cm, 2 * row_cm),
            dimension="length",
        ),
        meta=meta,
        bind_off=False,
        note_keys=tuple(note_keys),
        end_note_keys=tuple(end_keys),
    )
    area = sum(step.stitch_count_end for step in steps) / gauge.stitches_per_cm / gauge.rows_per_cm
    return _Built(section, plan, rows, area * piece.copies, piece)


def _build_skirt(dome: _Built, gauge: Gauge, craft: Craft) -> _Built:
    """Falda ondulada: sale de las hebras delanteras libres de la cupula,
    aumenta la mitad de los puntos y se remata."""
    count = dome.section.meta["max_stitches"]
    grown = count * 3 // 2  # un aumento cada 2 pts: la falda se ondula
    if craft == "crochet":
        ruffle = Repeat(count // 2, (Op(StitchKind.SC), Op(StitchKind.CROCHET_INC)))
        steps = [
            build_step(1, count, (ruffle,)),
            build_step(2, grown, (Op(StitchKind.SC, times=grown),)),
        ]
        end_keys: tuple[str, ...] = ("pattern.toy_skirt_end_crochet",)
    else:
        ruffle = Repeat(count // 2, (Op(StitchKind.KNIT), Op(StitchKind.KFB)))
        steps = [
            build_step(1, count, (ruffle,)),
            build_step(2, grown, (Op(StitchKind.PURL, times=grown),)),
            build_step(3, grown, (Op(StitchKind.KNIT, times=grown),)),
        ]
        end_keys = ("pattern.toy_skirt_end_knit",)
    section = Section(
        id="skirt",
        name_key="section.toy_skirt",
        mode="round" if craft == "crochet" else "flat",
        steps=tuple(steps),
        start_stitches=count,
        end_stitches=grown,
        meta={"row_count": len(steps), "toy": 1, "copies": 1, "max_stitches": grown, "base_units": 0, "picked_up": 1},
        note_keys=("pattern.note.toy_start_skirt." + craft,),
        end_note_keys=end_keys,
    )
    area = sum(step.stitch_count_end for step in steps) / gauge.stitches_per_cm / gauge.rows_per_cm
    plan = _Plan(counts=(count, grown), base_units=0)
    return _Built(section, plan, len(steps), area)


# ---------------------------------------------------------------------------
# Armado (numeros calculados a partir de las vueltas reales).
# ---------------------------------------------------------------------------


def _row_of(built: _Built, fraction: float) -> int:
    return max(2, min(built.rows - 1, round_half_up(built.rows * fraction)))


@dataclass(frozen=True)
class _Frame:
    """Tramo de una pieza que hace de cabeza o de cuerpo: vuelta de arriba
    (coronilla o cuello) y de abajo (menton o base). Puede ir al reves de
    como se teje (la pieza de una sola pieza empieza por la base)."""

    built: _Built
    top: int
    bottom: int

    def row(self, fraction: float) -> int:
        if self.top <= self.bottom:
            row = round_half_up(self.top - 1 + (self.bottom - self.top + 1) * fraction)
        else:
            row = round_half_up(self.top + 1 - (self.top - self.bottom + 1) * fraction)
        return max(2, min(self.built.rows - 1, row))

    def count(self, row: int) -> int:
        return self.built.count_at(row)

    def gap(self, row: int, fraction: float) -> int:
        return max(2, round_half_up(self.count(row) * fraction))


@dataclass(frozen=True)
class _Ctx:
    figure: Figure
    kit: FigureKit
    plan: PlanName
    craft: Craft
    built: dict[str, _Built]
    head: _Frame
    body: _Frame
    head_cm: float  # diametro de la cabeza armada
    units: str

    @property
    def scope(self) -> str:
        """`split`: cabeza y cuerpo son piezas distintas; `one`: una sola."""
        return "split" if self.head.built is not self.body.built else "one"

    def key(self, name: str) -> str:
        return f"finishing.toy.{name}.{self.craft}.{self.scope}"


def _fmt_len(cm: float, units: str) -> str:
    value = cm / 2.54 if units == "in" else cm
    return f"{round_half_up(value * 2) / 2:g} {units}"


# Ubicacion de cada parte (ASUNCION): fraccion del tramo de la cabeza desde la
# coronilla y separacion como fraccion de los puntos de esa vuelta.
EAR_PLACEMENT: dict[str, tuple[float, float]] = {
    "ear_round": (0.2, 0.3),
    "ear_pointy": (0.2, 0.3),
    "ear_long": (0.12, 0.15),
    "ear_floppy": (0.3, 0.42),
    "ear_flat": (0.35, 0.45),
    "ear_cup": (0.3, 0.42),
}
EYE_ROW = 0.56
EYE_GAP = 0.18


def _part_kinds(ctx: _Ctx) -> dict[str, str]:
    """id de pieza -> clase del kit, como quedo tejida."""
    out: dict[str, str] = {}
    for built in ctx.built.values():
        piece = built.piece
        if piece is not None and piece.id not in out:
            out[piece.id] = piece.variant or piece.id
    return out


def _head_notes(ctx: _Ctx) -> list[Note]:
    head, craft, kinds = ctx.head, ctx.craft, _part_kinds(ctx)
    split = ctx.scope == "split"
    notes: list[Note] = []
    eye_row = head.row(EYE_ROW)
    eye_gap = head.gap(eye_row, EYE_GAP)
    eye_mm = min(SAFETY_EYES_MM, key=lambda mm: abs(mm - ctx.head_cm * 1.05))
    if "eyebump" in ctx.built:
        row = head.row(0.15)
        bump_mm = min(SAFETY_EYES_MM, key=lambda mm: abs(mm - ctx.head_cm * 0.7))
        notes.append(Note(ctx.key("eyebumps"), {"a": row, "b": row + 1, "n": head.gap(row, 0.3), "mm": bump_mm}))
    else:
        eyes = f"finishing.toy.eyes.{craft}" if split else f"finishing.toy.ball_eyes.{craft}"
        notes.append(Note(eyes, {"a": eye_row, "b": eye_row + 1, "n": eye_gap, "mm": eye_mm}))
    snout = next((kinds[pid] for pid in ("muzzle", "trunk", "beak") if pid in kinds), None)
    if snout == "muzzle":
        key = f"finishing.toy.muzzle.{craft}" if split else ctx.key("muzzle")
        notes.append(Note(key, {"a": eye_row + 1}))
    elif snout in {"muzzle_pig", "muzzle_cow"}:
        notes.append(Note(ctx.key("muzzle_nostrils"), {"a": eye_row + 1}))
    elif snout is not None:
        notes.append(Note(ctx.key(snout), {"a": eye_row + 1}))
    if snout is None and ctx.kit.face != "none":
        notes.append(Note("finishing.toy." + ctx.kit.face, {}))
    if "ear" in kinds:
        kind = kinds["ear"]
        fraction, gap = EAR_PLACEMENT[kind]
        row = head.row(fraction)
        params: dict[str, str | int | float] = {"a": row, "b": row + 1, "n": head.gap(row, gap)}
        if kind in {"ear_round", "ear_pointy", "ear_long"}:
            name = ("ear" if split else "ball_ear") + ("_long" if kind == "ear_long" else "")
            notes.append(Note(f"finishing.toy.{name}.{craft}", params))
        else:
            notes.append(Note(ctx.key("ear_side"), params))
    if "horn" in kinds:
        spiral = kinds["horn"] == "horn_spiral"
        row = head.row(0.08 if spiral else 0.15)
        notes.append(Note(ctx.key("horn" if spiral else "horns"), {"a": row, "n": head.gap(row, 0.25)}))
    if "antenna" in kinds:
        row = head.row(0.15)
        notes.append(Note(ctx.key("antennae"), {"a": row, "n": head.gap(row, 0.2)}))
    notes.extend(_hair_notes(ctx))
    return notes


def _hair_notes(ctx: _Ctx) -> list[Note]:
    """Melena, pelo, crin y lana: cantidad y largo de hebras calculados."""
    hair, head = ctx.kit.hair, ctx.head
    if hair is None:
        return []
    step = 1 if ctx.craft == "crochet" else 2  # en agujas, sobre las hileras del derecho
    if hair == "mane":
        a, b = sorted((head.row(0.15), head.row(0.8)))
        rows = list(range(a, b + 1, 2 * step))
        strands = sum(head.count(r) // 4 for r in rows)  # media vuelta, un pt si y uno no
        length = _fmt_len(ctx.head_cm * 0.35 * 2, ctx.units)
        return [Note(ctx.key("mane"), {"a": rows[0], "b": rows[-1], "k": strands, "len": length})]
    if hair == "doll":
        a, b = sorted((head.row(0.0), head.row(0.45)))
        rows = list(range(a, b + 1, 2 * step))
        strands = sum(head.count(r) // 2 for r in rows)
        length = _fmt_len(ctx.head_cm * 1.6, ctx.units)
        return [Note(ctx.key("hair"), {"a": a, "b": b, "k": strands, "len": length})]
    if hair == "unicorn":
        a, b = sorted((head.row(0.05), head.row(0.7)))
        strands = len(range(a, b + 1, step)) * 2
        length = _fmt_len(ctx.head_cm * 0.9, ctx.units)
        tail_row = ctx.body.row(0.85)
        return [
            Note(ctx.key("mane_unicorn"), {"a": a, "b": b, "k": strands, "len": length}),
            Note(ctx.key("tail_hair"), {"a": tail_row, "k": max(8, ctx.body.count(tail_row) // 3), "len": _fmt_len(ctx.head_cm * 1.4, ctx.units)}),
        ]
    # Lana de oveja: lazadas sobre el cuerpo, cada n pts y cada 2 vueltas.
    a = ctx.body.row(0.0)
    every = max(2, round_half_up(ctx.body.built.section.meta["max_stitches"] / 12))
    return [Note(ctx.key("fleece"), {"a": a, "n": every})]


def _body_notes(ctx: _Ctx) -> list[Note]:
    """Partes que van en el cuerpo: cola, alas, aletas, caparazon, puas."""
    body, kinds = ctx.body, _part_kinds(ctx)
    notes: list[Note] = []
    if "wing" in kinds:
        row = body.row(0.2)
        notes.append(Note(ctx.key("wings_back" if ctx.figure is Figure.BEE else "wings"), {"a": row, "n": body.gap(row, 0.12)}))
    if "fin" in kinds:
        notes.append(Note(ctx.key("fins"), {"a": body.row(0.3)}))
    if "shell" in kinds:
        notes.append(Note(ctx.key("shell"), {"a": body.row(0.5)}))
    if "spine" in kinds:
        a, b = sorted((body.row(0.1), body.row(0.9)))
        spines = ctx.built["spine"].section.meta["copies"]
        notes.append(Note(ctx.key("spines"), {"a": a, "b": b, "k": spines, "n": max(1, (b - a) // max(1, spines - 1))}))
    if "fluke" in kinds:
        notes.append(Note(ctx.key("fluke"), {"a": 2 if ctx.plan == "snake" else body.row(0.85)}))
    if "tail" in kinds and kinds["tail"] == "tail_curly":
        notes.append(Note(ctx.key("tail_curly"), {"a": body.row(0.9)}))
    return notes


def _base_row(built: _Built, craft: Craft) -> int:
    """Borde de la base plana (o de la punta) de una pieza."""
    return max(2, built.row_of_unit(built.plan.base_units, craft))


def _assembly(ctx: _Ctx) -> tuple[Note, ...]:
    built, craft = ctx.built, ctx.craft
    notes = _head_notes(ctx)
    kinds = _part_kinds(ctx)
    tail_plain = "tail" in kinds and kinds["tail"] != "tail_curly"
    if ctx.plan in {"pieces", "biped", "seamless"}:
        # Sentado o de pie, con brazos y piernas (D033: mismos numeros).
        body = built["head_body" if ctx.plan == "seamless" else "body"]
        if ctx.plan != "seamless":
            notes.append(Note("finishing.toy.head_body", {}))
        neck = ctx.body.top
        notes.append(Note(f"finishing.toy.arms.{craft}", {"a": max(2, neck - (2 if craft == "crochet" else 4))}))
        base_row = _base_row(body, craft)
        leg_gap = max(2, round_half_up(body.section.meta["max_stitches"] * 0.2))
        legs = f"finishing.toy.legs.{craft}" if ctx.plan != "biped" else ctx.key("legs_stand")
        notes.append(Note(legs, {"a": base_row, "n": leg_gap}))
        notes.extend(_body_notes(ctx))
        if tail_plain:
            tail = f"finishing.toy.tail.{craft}" if ctx.scope == "split" else ctx.key("tail")
            notes.append(Note(tail, {"a": base_row + 2}))
    elif ctx.plan == "ball":
        ball = built["ball"]
        feet_row = _row_of(ball, 0.82)
        notes.append(Note(f"finishing.toy.ball_feet.{craft}", {"a": feet_row, "n": max(2, round_half_up(ball.count_at(feet_row) * 0.12))}))
        notes.extend(_body_notes(ctx))
        if tail_plain:
            notes.append(Note(f"finishing.toy.ball_tail.{craft}", {"a": _row_of(ball, 0.7)}))
    elif ctx.plan in {"quadruped", "dachshund"}:
        body = built["body"]
        notes.append(Note(ctx.key("head_front"), {"a": body.rows - 1}))
        front, back = ctx.body.row(0.2), ctx.body.row(0.8)
        notes.append(Note(ctx.key("legs4"), {"a": front, "b": back, "n": body.section.meta["max_stitches"] // 4}))
        notes.extend(_body_notes(ctx))
        if tail_plain:
            notes.append(Note(ctx.key("tail"), {"a": _base_row(body, craft)}))
    elif ctx.plan == "snake":
        notes.extend(_body_notes(ctx))
        if ctx.figure is Figure.GENERIC:
            notes.append(Note("finishing.toy.tongue", {}))
    else:  # radial
        dome = built["dome"]
        skirt_row = dome.row_of_unit(len(dome.plan.counts) - 1 - dome.plan.closing_units, craft)
        row = min(dome.rows - 1, skirt_row + 2)
        notes.append(Note(ctx.key("tentacles"), {"a": row, "n": dome.section.meta["max_stitches"] // TENTACLES}))
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


def toy_height(params: PatternParams, ball: bool = False, plan: PlanName | None = None) -> float:
    """Tamano del juguete (alto, o largo si es alargado)."""
    chosen: PlanName = plan or ("ball" if ball else "pieces")
    default = DEFAULT_HEIGHT_CM[params.peso_hilo] * PLAN_SIZE[chosen]
    keys = ("length", "height") if chosen in {"snake", "dachshund"} else ("height",)
    for key in keys:
        for source in (params.dimensiones_cm, params.medidas_cm):
            if key in source:
                return source[key]
    return default


# Medida de tamano de cada forma: clave de la medida (su rotulo) y del texto
# de la ficha tecnica.
SIZE_KEYS: dict[PlanName, str] = {
    "pieces": "toy_height",
    "ball": "toy_height_ball",
    "seamless": "toy_height",
    "biped": "toy_height_standing",
    "quadruped": "toy_height_standing",
    "dachshund": "toy_length",
    "snake": "toy_length",
    "radial": "toy_height_radial",
}
TOY_SIZE_MEASURES = frozenset(SIZE_KEYS.values())


def _cm(built: _Built, gauge: Gauge) -> float:
    return gauge.cm_for_rows(built.rows)


def _unit_cm(gauge: Gauge, craft: Craft) -> float:
    return gauge.cm_for_rows(1 if craft == "crochet" else 2)


def _rise_cm(built: _Built, gauge: Gauge, craft: Craft) -> float:
    """Altura que aporta una pieza armada (o largo, si va acostada)."""
    piece = built.piece
    assert piece is not None
    units = sum(
        u * seg.rise for u, seg in zip(built.plan.seg_units, piece.segs, strict=True)
    ) + built.plan.closing_units * DOME_RISE
    if craft == "crochet" and piece.segs[0].rise > 0:
        units += 1  # el anillo
    return units * _unit_cm(gauge, craft)


def _diam_rows(built: _Built, gauge: Gauge) -> float:
    return 2 * _cm(built, gauge) / pi


def _size_cm(plan: PlanName, built: dict[str, _Built], gauge: Gauge, craft: Craft) -> float:
    if plan == "ball":
        return _diam_rows(built["ball"], gauge)
    if plan == "pieces":
        head, body = built["head"], built["body"]
        base_cm = gauge.cm_for_rows(body.plan.base_units * (1 if craft == "crochet" else 2))
        return HEAD_VISIBLE * _diam_rows(head, gauge) + BODY_VISIBLE * (_cm(body, gauge) - base_cm)
    if plan == "seamless":
        return _rise_cm(built["head_body"], gauge, craft)
    if plan == "biped":
        leg = built["leg"]
        leg_d = gauge.cm_for_stitches(leg.section.meta["max_stitches"]) / pi
        return (
            HEAD_VISIBLE * _diam_rows(built["head"], gauge)
            + _rise_cm(built["body"], gauge, craft)
            + 0.95 * (_cm(leg, gauge) - leg_d / 2)
        )
    if plan == "quadruped":
        leg = built["leg"]
        leg_d = gauge.cm_for_stitches(leg.section.meta["max_stitches"]) / pi
        body_d = gauge.cm_for_stitches(built["body"].section.meta["max_stitches"]) / pi
        return 0.9 * (_cm(leg, gauge) - leg_d / 2) + body_d + 0.55 * _diam_rows(built["head"], gauge)
    if plan == "dachshund":
        return 0.95 * _cm(built["body"], gauge) + 0.6 * _diam_rows(built["head"], gauge)
    if plan == "snake":
        return _rise_cm(built["long"], gauge, craft)
    dome = built["dome"]
    return 0.9 * _diam_rows(dome, gauge) + 0.85 * _cm(built["tentacle"], gauge)


def _frames(plan: PlanName, built: dict[str, _Built], craft: Craft) -> tuple[_Frame, _Frame]:
    if "head" in built:
        head = built["head"]
        body = built["body"]
        return _Frame(head, 1, head.rows), _Frame(body, body.rows, 1)
    if plan == "ball":
        ball = built["ball"]
        return _Frame(ball, 1, round_half_up(ball.rows * 0.75)), _Frame(ball, round_half_up(ball.rows * 0.4), ball.rows)
    if plan == "seamless":
        piece = built["head_body"]
        neck = piece.seg_end_row(2, craft)
        return _Frame(piece, piece.rows, neck), _Frame(piece, neck, 1)
    if plan == "snake":
        piece = built["long"]
        segs = len(piece.plan.seg_units)
        neck = piece.seg_end_row(segs - 3, craft)
        # Cabeza acostada: la "coronilla" es la nuca y la cara mira a la punta.
        return _Frame(piece, neck, piece.rows), _Frame(piece, neck, 1)
    dome = built["dome"]
    return _Frame(dome, 1, dome.rows), _Frame(dome, round_half_up(dome.rows * 0.5), dome.rows)


def generate_amigurumi(spec: GarmentSpec, params: PatternParams) -> Pattern:
    """Juguete (crochet o dos agujas) segun la figura y la forma de cuerpo."""
    if spec.tecnica is Technique.CROCHET:
        craft: Craft = "crochet"
    elif spec.tecnica in {Technique.NEEDLES, Technique.CIRCULAR}:
        craft = "knit"
    else:
        raise ImpossibleProportionsError("error.unsupported_technique", technique=spec.tecnica.value)
    figure = spec.figura or Figure.GENERIC
    kit = FIGURES[figure]
    body_kind, overridden = resolve_body(figure, spec.cuerpo_juguete)
    plan = _plan_name(body_kind, kit)
    params = _toy_params(params, craft)
    gauge = params.densidad
    assert gauge is not None
    size = toy_height(params, plan=plan)
    pieces = toy_pieces(figure, body_kind)
    built: dict[str, _Built] = {}
    for piece in pieces:
        built[piece.id] = _build_section(piece, size, gauge, craft, dome_back_loop=piece.id == "dome")
    if plan == "radial":
        built["skirt"] = _build_skirt(built["dome"], gauge, craft)
    main = built[pieces[0].id]
    sectors = SECTORS[craft]
    too_small = ImpossibleProportionsError(
        "error.too_small_for_yarn", weight=params.peso_hilo.value, target=round(size, 1)
    )
    if main.section.meta["max_stitches"] < 4 * sectors:
        raise too_small
    for item in built.values():
        section = item.section
        if section.target is None:
            continue
        actual = gauge.cm_for_rows(item.rows)
        if abs(actual - section.target.target_cm) > section.target.tolerance_cm:
            raise too_small
    head_frame, body_frame = _frames(plan, built, craft)
    head_cm = gauge.cm_for_stitches(head_frame.count(head_frame.row(0.5))) / pi
    ctx = _Ctx(figure, kit, plan, craft, built, head_frame, body_frame, head_cm, params.unidades)
    measurements = _measurements(plan, pieces, built, gauge, craft, size)
    finishing = _assembly(ctx)
    generic = spec.figura is None
    spec = spec.model_copy(update={"figura": figure, "cuerpo_juguete": body_kind})
    return _toy_pattern(spec, params, craft, figure, plan, built, measurements, finishing, overridden, generic)


def _measurements(
    plan: PlanName,
    pieces: tuple[PieceTemplate, ...],
    built: dict[str, _Built],
    gauge: Gauge,
    craft: Craft,
    size: float,
) -> tuple[Measurement, ...]:
    out = [
        Measurement(
            key=SIZE_KEYS[plan],
            value_cm=_size_cm(plan, built, gauge, craft),
            target_cm=(PROPORTIONS["ball"]["ball"] if plan == "ball" else 1.0) * size,
            tolerance_cm=max(1.5, 0.12 * size),
            kind="length",
        )
    ]
    for piece in pieces[:2]:
        if piece.id in {"head", "dome", "ball", "body", "head_body", "long"}:
            key = "toy_head" if piece.id in {"head", "dome"} else "toy_body"
            if any(m.key == key for m in out):
                continue
            circ = max(seg.circ for seg in piece.segs) * size
            out.append(
                Measurement(
                    key=key,
                    value_cm=gauge.cm_for_stitches(built[piece.id].section.meta["max_stitches"]),
                    target_cm=circ,
                    tolerance_cm=max(1.5, 0.15 * circ),
                    kind="circumference",
                )
            )
    return tuple(out)


def _toy_pattern(
    spec: GarmentSpec,
    params: PatternParams,
    craft: Craft,
    figure: Figure,
    plan: PlanName,
    built: dict[str, _Built],
    measurements: tuple[Measurement, ...],
    finishing: tuple[Note, ...],
    overridden: bool,
    generic: bool,
) -> Pattern:
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
    proportions = {
        "pieces": "warning.toy_proportions",
        "ball": "warning.toy_proportions_ball",
    }.get(plan, f"warning.toy_proportions_{plan}")
    warnings = [
        Warning(f"toy_construction_{craft}", f"warning.toy_construction.{craft}", severity="info"),
        Warning("toy_tight", f"warning.toy_tight.{craft}", severity="info"),
        Warning("toy_safety", "warning.toy_safety", severity="warning"),
        Warning("estimated_yardage", "warning.estimated_yardage", severity="info"),
        Warning("assumption", proportions, severity="info"),
    ]
    if overridden:
        body = spec.cuerpo_juguete.value if spec.cuerpo_juguete else "pieces"
        warnings.append(Warning("toy_body_override", f"warning.toy_body_override.{body}", severity="info"))
    if generic:
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
        finishing=finishing,
    )


__all__ = [
    "DEFAULT_HEIGHT_CM",
    "FIGURES",
    "PARTS",
    "PROPORTIONS",
    "SECTORS",
    "SIZE_KEYS",
    "TEMPLATES",
    "TOY_SIZE_MEASURES",
    "generate_amigurumi",
    "pattern_plan",
    "resolve_body",
    "toy_description_keys",
    "toy_height",
    "toy_pieces",
    "toy_plan",
]
