"""Tipos atomicos de punto y su efecto en el conteo.

El efecto es la unica fuente de verdad que usa el simulador: cuantos puntos
consume y cuantos produce cada instruccion. Toda instruccion del IR es un
`Op` con uno de estos tipos.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StitchKind(StrEnum):
    # Dos agujas / circular
    KNIT = "knit"
    PURL = "purl"
    K1TBL = "k1tbl"
    P1TBL = "p1tbl"
    K2TOG = "k2tog"
    SSK = "ssk"
    P2TOG = "p2tog"
    SSP = "ssp"
    YO = "yo"
    M1L = "m1l"
    M1R = "m1r"
    KFB = "kfb"
    SL1 = "sl1"
    CABLE_FRONT = "cable_front"
    CABLE_BACK = "cable_back"
    BOBBLE = "bobble"
    BRIOCHE_KNIT = "brioche_knit"
    BRIOCHE_PURL = "brioche_purl"
    TURN = "turn"
    CAST_ON = "cast_on"
    BIND_OFF = "bind_off"  # cerrar puntos en medio de una pieza (sisa, copa)

    # Crochet
    SC = "sc"
    HDC = "hdc"
    DC = "dc"
    CH = "ch"
    SLST = "slst"
    CROCHET_INC = "crochet_inc"
    CROCHET_DEC = "crochet_dec"
    MAGIC_RING = "magic_ring"
    RING = "ring"  # anillo magico con `width` pts del punto de la pieza
    # Motivos (engine/garments/motif.py).
    TR = "tr"  # punto alto doble
    SKIP = "skip"  # saltar 1 pt
    CLUSTER = "cluster"  # 3 pa cerrados juntos en el mismo pt
    POPCORN = "popcorn"  # 5 pa en el mismo pt, cerrados como pop
    PUFF = "puff"  # punto puff (3 lazadas sacadas en el mismo pt)
    CORNER_SC = "corner_sc"  # (1 pt, 2 cad, 1 pt) en el esp de esquina
    CORNER_DC = "corner_dc"  # (2 pts, 2 cad, 2 pts) en el esp de esquina
    SQUARE_TURN = "square_turn"  # (2 pad, 2 cad, 2 pad) en el mismo pt
    # Granny square clasico, trabajado en los espacios de la vuelta anterior.
    GRANNY_START = "granny_start"
    GRANNY_CORNER = "granny_corner"
    GRANNY_SIDE = "granny_side"
    # Hogar (engine/garments/home.py): puntos tejidos sobre un borde (el otro
    # lado de la cadena base, los extremos de las hileras) que no consumen
    # puntos vivos: suman un punto nuevo cada uno.
    CROCHET_EDGE = "crochet_edge"
    PICK_UP = "pick_up"


@dataclass(frozen=True)
class Effect:
    consumes: int
    produces: int

    @property
    def delta(self) -> int:
        return self.produces - self.consumes


_EFFECTS: dict[StitchKind, Effect] = {
    StitchKind.KNIT: Effect(1, 1),
    StitchKind.PURL: Effect(1, 1),
    StitchKind.K1TBL: Effect(1, 1),
    StitchKind.P1TBL: Effect(1, 1),
    StitchKind.K2TOG: Effect(2, 1),
    StitchKind.SSK: Effect(2, 1),
    StitchKind.P2TOG: Effect(2, 1),
    StitchKind.SSP: Effect(2, 1),
    StitchKind.YO: Effect(0, 1),
    StitchKind.M1L: Effect(0, 1),
    StitchKind.M1R: Effect(0, 1),
    StitchKind.KFB: Effect(1, 2),
    StitchKind.SL1: Effect(1, 1),
    StitchKind.BOBBLE: Effect(1, 1),
    # Representacion atomica de una columna de canale ingles: consume y
    # produce un punto por vuelta. El texto explica la tecnica completa.
    StitchKind.BRIOCHE_KNIT: Effect(1, 1),
    StitchKind.BRIOCHE_PURL: Effect(1, 1),
    StitchKind.TURN: Effect(0, 0),
    StitchKind.CAST_ON: Effect(0, 1),
    StitchKind.BIND_OFF: Effect(1, 0),
    StitchKind.SC: Effect(1, 1),
    StitchKind.HDC: Effect(1, 1),
    StitchKind.DC: Effect(1, 1),
    StitchKind.CH: Effect(0, 1),
    StitchKind.SLST: Effect(1, 1),
    StitchKind.CROCHET_INC: Effect(1, 2),
    StitchKind.CROCHET_DEC: Effect(2, 1),
    # Supuesto de amigurumi: anillo magico con 6 puntos bajos iniciales.
    StitchKind.MAGIC_RING: Effect(0, 6),
    # Granny: cada grupo cuenta sus pa y cad. Trabajar en un espacio "consume"
    # el grupo de 3 pa anterior y las cadenas del espacio (asi cada vuelta
    # consume exactamente la anterior). Vuelta n: 12n pa + 4n+4 cad = 16n+4.
    StitchKind.GRANNY_START: Effect(0, 5),  # en el anillo: 3 pa, 2 cad
    StitchKind.GRANNY_CORNER: Effect(5, 9),  # esquina: 3 pa, 2 cad, 3 pa, 1 cad
    StitchKind.GRANNY_SIDE: Effect(4, 4),  # lado: 3 pa en el esp, 1 cad
    StitchKind.TR: Effect(1, 1),
    StitchKind.SKIP: Effect(1, 0),
    StitchKind.CLUSTER: Effect(1, 1),
    StitchKind.POPCORN: Effect(1, 1),
    StitchKind.PUFF: Effect(1, 1),
    # Esquinas de un cuadrado: las 2 cad del espacio de la vuelta anterior se
    # "consumen" y se producen los pts del grupo (como en el granny).
    StitchKind.CORNER_SC: Effect(2, 4),
    StitchKind.CORNER_DC: Effect(2, 6),
    StitchKind.SQUARE_TURN: Effect(1, 6),
    StitchKind.CROCHET_EDGE: Effect(0, 1),
    StitchKind.PICK_UP: Effect(0, 1),
}

_CABLES = {StitchKind.CABLE_FRONT, StitchKind.CABLE_BACK}


def stitch_effect(kind: StitchKind, width: int | None = None) -> Effect:
    """Efecto de un punto. Los cables consumen y producen `width` puntos."""
    if kind is StitchKind.RING:
        if width is None or width < 3:
            raise ValueError(f"anillo: al menos 3 pts, no {width!r}")
        return Effect(0, width)
    if kind in _CABLES:
        if width is None or width < 2 or width % 2 != 0:
            raise ValueError(f"cable {kind.value}: ancho par >= 2 requerido, no {width!r}")
        return Effect(width, width)
    return _EFFECTS[kind]
