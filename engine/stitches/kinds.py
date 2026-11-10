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

    # Crochet
    SC = "sc"
    HDC = "hdc"
    DC = "dc"
    CH = "ch"
    SLST = "slst"
    CROCHET_INC = "crochet_inc"
    CROCHET_DEC = "crochet_dec"
    MAGIC_RING = "magic_ring"


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
    StitchKind.SC: Effect(1, 1),
    StitchKind.HDC: Effect(1, 1),
    StitchKind.DC: Effect(1, 1),
    StitchKind.CH: Effect(0, 1),
    StitchKind.SLST: Effect(1, 1),
    StitchKind.CROCHET_INC: Effect(1, 2),
    StitchKind.CROCHET_DEC: Effect(2, 1),
    # Supuesto de amigurumi: anillo magico con 6 puntos bajos iniciales.
    StitchKind.MAGIC_RING: Effect(0, 6),
}

_CABLES = {StitchKind.CABLE_FRONT, StitchKind.CABLE_BACK}


def stitch_effect(kind: StitchKind, width: int | None = None) -> Effect:
    """Efecto de un punto. Los cables consumen y producen `width` puntos."""
    if kind in _CABLES:
        if width is None or width < 2 or width % 2 != 0:
            raise ValueError(f"cable {kind.value}: ancho par >= 2 requerido, no {width!r}")
        return Effect(width, width)
    return _EFFECTS[kind]
