"""Catalogo declarativo de puntos.

Cada entrada describe un motivo repetible de ancho `multiple` y sus vueltas.
El motor de prendas ajusta los conteos a multiplos de `multiple`. Las
instrucciones y los graficos salen de las mismas operaciones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from engine.ir import Op
from engine.rounding import round_half_up
from engine.spec import StitchPatternName
from engine.stitches.chart import ChartCell, chart_cells_from_ops
from engine.stitches.kinds import StitchKind


@dataclass(frozen=True)
class StitchPattern:
    id: str
    name_key: str
    technique: Literal["needles", "crochet"]
    multiple: int
    rows: tuple[tuple[Op, ...], ...]
    round_rows: tuple[tuple[Op, ...], ...] | None = None
    setup_ops: tuple[Op, ...] = ()
    notes_key: str | None = None

    def __post_init__(self) -> None:
        if self.multiple < 1:
            raise ValueError("multiple debe ser >= 1")
        if not self.rows:
            raise ValueError("el patron necesita al menos una vuelta")
        if self.round_rows is not None and not self.round_rows:
            raise ValueError("round_rows no puede estar vacio")

    @property
    def row_repeat(self) -> int:
        return len(self.rows)

    def row_count(self, *, in_the_round: bool = False) -> int:
        if in_the_round and self.round_rows is not None:
            return len(self.round_rows)
        return len(self.rows)

    def ops_for_row(self, row_number: int, *, in_the_round: bool = False) -> tuple[Op, ...]:
        if row_number < 1:
            raise ValueError("row_number empieza en 1")
        rows = self.round_rows if in_the_round and self.round_rows is not None else self.rows
        return rows[(row_number - 1) % len(rows)]

    def chart_cells(self, row_number: int, *, in_the_round: bool = False) -> tuple[ChartCell, ...]:
        return chart_cells_from_ops(self.ops_for_row(row_number, in_the_round=in_the_round))


def K(times: int = 1) -> Op:
    return Op(StitchKind.KNIT, times=times)


def P(times: int = 1) -> Op:
    return Op(StitchKind.PURL, times=times)


def _cable(kind: StitchKind, width: int) -> Op:
    return Op(kind, width=width)


STITCH_PATTERNS: dict[str, StitchPattern] = {
    "stockinette": StitchPattern(
        id="stockinette",
        name_key="stitch.stockinette",
        technique="needles",
        multiple=1,
        rows=((K(),), (P(),)),
        round_rows=((K(),), (K(),)),
    ),
    "garter": StitchPattern(
        id="garter",
        name_key="stitch.garter",
        technique="needles",
        multiple=1,
        rows=((K(),), (K(),)),
        round_rows=((K(),), (P(),)),
    ),
    "seed": StitchPattern(
        id="seed",
        name_key="stitch.seed",
        technique="needles",
        multiple=2,
        rows=((K(), P()), (P(), K())),
    ),
    "moss": StitchPattern(
        id="moss",
        name_key="stitch.moss",
        technique="needles",
        multiple=4,
        rows=((K(2), P(2)), (K(2), P(2)), (P(2), K(2)), (P(2), K(2))),
    ),
    "rib_1x1": StitchPattern(
        id="rib_1x1",
        name_key="stitch.rib_1x1",
        technique="needles",
        multiple=2,
        rows=((K(), P()), (P(), K())),
        round_rows=((K(), P()),),
    ),
    "rib_2x2": StitchPattern(
        id="rib_2x2",
        name_key="stitch.rib_2x2",
        technique="needles",
        multiple=4,
        rows=((K(2), P(2)), (P(2), K(2))),
        round_rows=((K(2), P(2)),),
    ),
    "rib_3x1": StitchPattern(
        id="rib_3x1",
        name_key="stitch.rib_3x1",
        technique="needles",
        multiple=4,
        rows=((K(3), P()), (P(3), K())),
        round_rows=((K(3), P()),),
    ),
    "brioche": StitchPattern(
        id="brioche",
        name_key="stitch.brioche",
        technique="needles",
        multiple=2,
        rows=(
            (Op(StitchKind.BRIOCHE_KNIT), Op(StitchKind.BRIOCHE_PURL)),
            (Op(StitchKind.BRIOCHE_PURL), Op(StitchKind.BRIOCHE_KNIT)),
        ),
        round_rows=(
            (Op(StitchKind.BRIOCHE_KNIT), Op(StitchKind.BRIOCHE_PURL)),
        ),
        notes_key="stitch.note.brioche",
    ),
    "cable_2x2_front": StitchPattern(
        id="cable_2x2_front",
        name_key="stitch.cables",
        technique="needles",
        multiple=4,
        rows=(
            (K(4),),
            (P(4),),
            (_cable(StitchKind.CABLE_FRONT, 4),),
            (P(4),),
        ),
        notes_key="stitch.note.cable",
    ),
    "cable_2x2_back": StitchPattern(
        id="cable_2x2_back",
        name_key="stitch.cables",
        technique="needles",
        multiple=4,
        rows=(
            (K(4),),
            (P(4),),
            (_cable(StitchKind.CABLE_BACK, 4),),
            (P(4),),
        ),
        notes_key="stitch.note.cable",
    ),
    "cable_3x3_front": StitchPattern(
        id="cable_3x3_front",
        name_key="stitch.cables",
        technique="needles",
        multiple=6,
        rows=(
            (K(6),),
            (P(6),),
            (_cable(StitchKind.CABLE_FRONT, 6),),
            (P(6),),
        ),
        notes_key="stitch.note.cable",
    ),
    "cable_3x3_back": StitchPattern(
        id="cable_3x3_back",
        name_key="stitch.cables",
        technique="needles",
        multiple=6,
        rows=(
            (K(6),),
            (P(6),),
            (_cable(StitchKind.CABLE_BACK, 6),),
            (P(6),),
        ),
        notes_key="stitch.note.cable",
    ),
    "eyelet": StitchPattern(
        id="eyelet",
        name_key="stitch.lace",
        technique="needles",
        multiple=4,
        rows=(
            (Op(StitchKind.K2TOG), Op(StitchKind.YO), K(2)),
            (P(4),),
        ),
    ),
    "lace_basic": StitchPattern(
        id="lace_basic",
        name_key="stitch.lace",
        technique="needles",
        multiple=6,
        rows=(
            (K(), Op(StitchKind.YO), Op(StitchKind.SSK), K(3)),
            (P(6),),
            (K(2), Op(StitchKind.YO), Op(StitchKind.SSK), K(2)),
            (P(6),),
        ),
    ),
    "bobbles": StitchPattern(
        id="bobbles",
        name_key="stitch.bobbles",
        technique="needles",
        multiple=6,
        rows=(
            (K(), Op(StitchKind.BOBBLE), K(4)),
            (P(6),),
            (K(6),),
            (P(6),),
            (K(6),),
            (P(6),),
        ),
    ),
    "honeycomb": StitchPattern(
        id="honeycomb",
        name_key="stitch.honeycomb",
        technique="needles",
        multiple=4,
        rows=(
            (K(4),),
            (P(4),),
            (_cable(StitchKind.CABLE_BACK, 4),),
            (P(4),),
            (K(4),),
            (P(4),),
            (_cable(StitchKind.CABLE_FRONT, 4),),
            (P(4),),
        ),
        notes_key="stitch.note.honeycomb",
    ),
    "crochet_sc": StitchPattern(
        id="crochet_sc",
        name_key="stitch.crochet_sc",
        technique="crochet",
        multiple=1,
        rows=((Op(StitchKind.SC),),),
        notes_key="stitch.note.crochet",
    ),
    "crochet_hdc": StitchPattern(
        id="crochet_hdc",
        name_key="stitch.crochet_hdc",
        technique="crochet",
        multiple=1,
        rows=((Op(StitchKind.HDC),),),
        notes_key="stitch.note.crochet",
    ),
    "crochet_dc": StitchPattern(
        id="crochet_dc",
        name_key="stitch.crochet_dc",
        technique="crochet",
        multiple=1,
        rows=((Op(StitchKind.DC),),),
        notes_key="stitch.note.crochet",
    ),
    "magic_ring": StitchPattern(
        id="magic_ring",
        name_key="stitch.crochet_sc",
        technique="crochet",
        multiple=6,
        rows=((Op(StitchKind.SC, times=6),),),
        setup_ops=(Op(StitchKind.MAGIC_RING),),
        notes_key="stitch.note.magic_ring",
    ),
}

_PATTERN_NAME_TO_ID: dict[StitchPatternName, str] = {
    StitchPatternName.STOCKINETTE: "stockinette",
    StitchPatternName.GARTER: "garter",
    StitchPatternName.SEED: "seed",
    StitchPatternName.RIB_1X1: "rib_1x1",
    StitchPatternName.RIB_2X2: "rib_2x2",
    StitchPatternName.RIB_3X1: "rib_3x1",
    StitchPatternName.MOSS: "moss",
    StitchPatternName.BRIOCHE: "brioche",
    StitchPatternName.CABLES: "cable_2x2_front",
    StitchPatternName.LACE: "lace_basic",
    StitchPatternName.BOBBLES: "bobbles",
    StitchPatternName.HONEYCOMB: "honeycomb",
    StitchPatternName.CROCHET_SC: "crochet_sc",
    StitchPatternName.CROCHET_HDC: "crochet_hdc",
    StitchPatternName.CROCHET_DC: "crochet_dc",
    StitchPatternName.OTHER: "stockinette",
}


def get_stitch(pattern_id: str) -> StitchPattern:
    try:
        return STITCH_PATTERNS[pattern_id]
    except KeyError as exc:
        raise KeyError(f"punto desconocido: {pattern_id!r}") from exc


def catalog_id_for_name(name: StitchPatternName) -> str:
    return _PATTERN_NAME_TO_ID[name]


def adjust_stitches(stitches: int, multiple: int, *, mode: str = "nearest") -> int:
    """Ajusta un conteo al multiplo del motivo.

    mode="nearest" redondea half-up; mode="up" siempre sube.
    """
    if multiple < 1:
        raise ValueError("multiple debe ser >= 1")
    if stitches < 0:
        raise ValueError("stitches no puede ser negativo")
    if mode == "up":
        return max(multiple, ((stitches + multiple - 1) // multiple) * multiple)
    if mode == "nearest":
        return max(multiple, round_half_up(stitches / multiple) * multiple)
    raise ValueError(f"modo desconocido: {mode!r}")


def expand_row(
    pattern: StitchPattern,
    stitches: int,
    row_number: int,
    *,
    in_the_round: bool = False,
) -> tuple[Op, ...]:
    """Expande una vuelta del motivo a un ancho de `stitches` puntos."""
    if stitches <= 0:
        raise ValueError("stitches debe ser > 0")
    if stitches % pattern.multiple != 0:
        raise ValueError(
            f"{pattern.id}: {stitches} no es multiplo de {pattern.multiple}"
        )
    repeats = stitches // pattern.multiple
    base_ops = pattern.ops_for_row(row_number, in_the_round=in_the_round)
    expanded: list[Op] = []
    for op in base_ops:
        expanded.append(Op(op.kind, times=op.times * repeats, width=op.width))
    consumed = sum(op.consumes for op in expanded)
    produced = sum(op.produces for op in expanded)
    if consumed != stitches or produced != stitches:
        raise ValueError(
            f"{pattern.id} vuelta {row_number}: consume {consumed}, produce "
            f"{produced}, se esperaban {stitches}"
        )
    return tuple(expanded)


def validate_catalog() -> list[str]:
    """Devuelve una lista de problemas; vacia si el catalogo es consistente."""
    problems: list[str] = []
    for pattern in STITCH_PATTERNS.values():
        for index, row in enumerate(pattern.rows, start=1):
            consumed = sum(op.consumes for op in row)
            produced = sum(op.produces for op in row)
            if consumed != pattern.multiple or produced != pattern.multiple:
                problems.append(
                    f"{pattern.id} fila {index}: consume {consumed}, produce "
                    f"{produced}, multiple {pattern.multiple}"
                )
            cells = pattern.chart_cells(index)
            if sum(cell.span for cell in cells) != pattern.multiple:
                problems.append(
                    f"{pattern.id} fila {index}: el grafico suma "
                    f"{sum(cell.span for cell in cells)} celdas"
                )
        if pattern.round_rows is not None:
            for index, row in enumerate(pattern.round_rows, start=1):
                consumed = sum(op.consumes for op in row)
                produced = sum(op.produces for op in row)
                if consumed != pattern.multiple or produced != pattern.multiple:
                    problems.append(
                        f"{pattern.id} vuelta circular {index}: consume "
                        f"{consumed}, produce {produced}"
                    )
    return problems
