"""Simbolos de grafico derivados de las operaciones del IR."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from engine.ir import Op
from engine.stitches.kinds import StitchKind


class ChartSymbol(StrEnum):
    KNIT = "knit"
    PURL = "purl"
    K2TOG = "k2tog"
    SSK = "ssk"
    YO = "yo"
    CABLE_FRONT = "cable_front"
    CABLE_BACK = "cable_back"
    BOBBLE = "bobble"
    SLIP = "slip"
    INCREASE_LEFT = "increase_left"
    INCREASE_RIGHT = "increase_right"
    KFB = "kfb"
    SC = "sc"
    HDC = "hdc"
    DC = "dc"
    CH = "ch"
    MAGIC_RING = "magic_ring"
    BRIOCHE_KNIT = "brioche_knit"
    BRIOCHE_PURL = "brioche_purl"
    CROCHET_INC = "crochet_inc"
    CROCHET_DEC = "crochet_dec"
    CAST_ON = "cast_on"
    TURN = "turn"
    TWISTED_KNIT = "twisted_knit"
    TWISTED_PURL = "twisted_purl"
    SLIP_WYIF = "slip_wyif"
    SC_BLO = "sc_blo"
    TR = "tr"
    V_STITCH = "v_stitch"
    SHELL = "shell"
    GRANNY_GROUP = "granny_group"
    TSS = "tss"
    C2C_BLOCK = "c2c_block"


_SYMBOL_BY_KIND: dict[StitchKind, ChartSymbol] = {
    StitchKind.KNIT: ChartSymbol.KNIT,
    StitchKind.PURL: ChartSymbol.PURL,
    StitchKind.K1TBL: ChartSymbol.TWISTED_KNIT,
    StitchKind.P1TBL: ChartSymbol.TWISTED_PURL,
    StitchKind.K2TOG: ChartSymbol.K2TOG,
    StitchKind.P2TOG: ChartSymbol.K2TOG,
    StitchKind.SSK: ChartSymbol.SSK,
    StitchKind.SSP: ChartSymbol.SSK,
    StitchKind.YO: ChartSymbol.YO,
    StitchKind.M1L: ChartSymbol.INCREASE_LEFT,
    StitchKind.M1R: ChartSymbol.INCREASE_RIGHT,
    StitchKind.KFB: ChartSymbol.KFB,
    StitchKind.SL1: ChartSymbol.SLIP,
    StitchKind.CABLE_FRONT: ChartSymbol.CABLE_FRONT,
    StitchKind.CABLE_BACK: ChartSymbol.CABLE_BACK,
    StitchKind.BOBBLE: ChartSymbol.BOBBLE,
    StitchKind.BRIOCHE_KNIT: ChartSymbol.BRIOCHE_KNIT,
    StitchKind.BRIOCHE_PURL: ChartSymbol.BRIOCHE_PURL,
    StitchKind.SC: ChartSymbol.SC,
    StitchKind.HDC: ChartSymbol.HDC,
    StitchKind.DC: ChartSymbol.DC,
    StitchKind.CH: ChartSymbol.CH,
    StitchKind.SLST: ChartSymbol.SLIP,
    StitchKind.CROCHET_INC: ChartSymbol.CROCHET_INC,
    StitchKind.CROCHET_DEC: ChartSymbol.CROCHET_DEC,
    StitchKind.MAGIC_RING: ChartSymbol.MAGIC_RING,
    StitchKind.CAST_ON: ChartSymbol.CAST_ON,
    StitchKind.TURN: ChartSymbol.TURN,
    StitchKind.SL1_WYIF: ChartSymbol.SLIP_WYIF,
    StitchKind.SL1_WYIB: ChartSymbol.SLIP,
    StitchKind.SC_BLO: ChartSymbol.SC_BLO,
    StitchKind.TR: ChartSymbol.TR,
    StitchKind.V_STITCH: ChartSymbol.V_STITCH,
    StitchKind.SHELL: ChartSymbol.SHELL,
    StitchKind.GRANNY_GROUP: ChartSymbol.GRANNY_GROUP,
    StitchKind.TSS: ChartSymbol.TSS,
    StitchKind.C2C_NEW: ChartSymbol.C2C_BLOCK,
    StitchKind.C2C_BLOCK: ChartSymbol.C2C_BLOCK,
}
# Sin casilla propia: saltar un pt, la pasada de vuelta del tunecino y los
# movimientos del C2C no producen puntos (el grafico muestra lo que queda).
_NO_CELL = {StitchKind.SKIP, StitchKind.TUNISIAN_RETURN, StitchKind.C2C_SLIDE, StitchKind.C2C_TURN}
# Grupos que se tejen en un pt: una casilla tan ancha como los pts que dejan.
_GROUPS = {StitchKind.V_STITCH, StitchKind.SHELL, StitchKind.GRANNY_GROUP}


@dataclass(frozen=True)
class ChartCell:
    symbol: ChartSymbol
    span: int = 1


def _cells_for_op(op: Op) -> list[ChartCell]:
    if op.kind in _NO_CELL:
        return []
    if op.kind in _GROUPS:
        return [ChartCell(_SYMBOL_BY_KIND[op.kind], span=op.produces // op.times)] * op.times
    symbol = _SYMBOL_BY_KIND.get(op.kind)
    if symbol is None:
        raise ValueError(f"no hay simbolo de grafico para {op.kind.value}")
    if op.kind in {StitchKind.CABLE_FRONT, StitchKind.CABLE_BACK}:
        return [ChartCell(symbol, span=op.width or 1)] * op.times
    if op.kind is StitchKind.KFB:
        return [ChartCell(symbol, span=2)] * op.times
    if op.kind is StitchKind.MAGIC_RING:
        return [ChartCell(symbol, span=op.produces)] * op.times
    return [ChartCell(symbol, span=1)] * op.times


def chart_cells_from_ops(ops: tuple[Op, ...]) -> tuple[ChartCell, ...]:
    cells: list[ChartCell] = []
    for op in ops:
        cells.extend(_cells_for_op(op))
    return tuple(cells)
