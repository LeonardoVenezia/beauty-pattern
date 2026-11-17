"""Catalogo declarativo de puntos.

Cada entrada describe un motivo repetible de ancho `multiple` y sus vueltas.
El motor de prendas ajusta los conteos a multiplos de `multiple`. Las
instrucciones y los graficos salen de las mismas operaciones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from engine.ir import Item, Op, Repeat
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
    # Ops que cierran cada vuelta una sola vez (no por repeticion): la pasada
    # de vuelta del tunecino. No cambian el conteo.
    row_end: tuple[Op, ...] = ()
    # (pts, vueltas) por 10 cm relativos a la densidad de referencia del hilo
    # en jersey (dos agujas). Crochet: ver engine/gauge.py::_CROCHET_SHAPE.
    gauge_factor: tuple[float, float] = (1.0, 1.0)

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


_SWAP = {
    StitchKind.KNIT: StitchKind.PURL,
    StitchKind.PURL: StitchKind.KNIT,
    StitchKind.K1TBL: StitchKind.P1TBL,
    StitchKind.P1TBL: StitchKind.K1TBL,
}


def _in_the_round(rows: tuple[tuple[Op, ...], ...]) -> tuple[tuple[Op, ...], ...]:
    """Hileras planas -> vueltas en redondo: las pares (LR) se leen al reves
    y con el punto contrario (der <-> rev), porque en redondo siempre se teje
    del LD."""
    return tuple(
        row if index % 2 == 0 else tuple(Op(_SWAP[op.kind], times=op.times) for op in reversed(row))
        for index, row in enumerate(rows)
    )


def rs_view_rows(rows: tuple[tuple[Op, ...], ...]) -> tuple[tuple[Op, ...], ...]:
    """Hileras planas vistas del LD (para el grafico): igual que en redondo."""
    return _in_the_round(rows)


def _op(kind: StitchKind, times: int = 1) -> Op:
    return Op(kind, times=times)


# Cesteria (Barbara Walker, "Basketweave", adaptada a multiplo de 8): bloques
# de 3 derechos rodeados de reveses, alternados cada 4 hileras.
_BASKETWEAVE_ROWS: tuple[tuple[Op, ...], ...] = (
    (K(8),),
    (K(5), P(3)),
    (K(3), P(5)),
    (K(5), P(3)),
    (K(8),),
    (K(), P(3), K(4)),
    (P(4), K(3), P()),
    (K(), P(3), K(4)),
)
# Punto waffle (gofre) de dos agujas, multiplo de 3.
_WAFFLE_ROWS: tuple[tuple[Op, ...], ...] = ((K(2), P()), (K(), P(2)), (K(2), P()), (K(3),))


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
        name_key="stitch.seed_named",
        technique="needles",
        multiple=2,
        rows=((K(), P()), (P(), K())),
    ),
    "moss": StitchPattern(
        id="moss",
        name_key="stitch.moss_named",
        technique="needles",
        multiple=4,
        rows=((K(2), P(2)), (K(2), P(2)), (P(2), K(2)), (P(2), K(2))),
    ),
    "rib_1x1": StitchPattern(
        id="rib_1x1",
        name_key="stitch.rib_1x1",
        technique="needles",
        multiple=2,
        rows=((K(), P()), (K(), P())),
        round_rows=((K(), P()),),
    ),
    "rib_2x2": StitchPattern(
        id="rib_2x2",
        name_key="stitch.rib_2x2",
        technique="needles",
        multiple=4,
        rows=((K(2), P(2)), (K(2), P(2))),
        round_rows=((K(2), P(2)),),
    ),
    "rib_3x1": StitchPattern(
        id="rib_3x1",
        name_key="stitch.rib_3x1",
        technique="needles",
        multiple=4,
        rows=((K(3), P()), (K(), P(3))),
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
        round_rows=((Op(StitchKind.BRIOCHE_KNIT), Op(StitchKind.BRIOCHE_PURL)),),
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
    "reverse_stockinette": StitchPattern(
        id="reverse_stockinette",
        name_key="stitch.reverse_stockinette",
        technique="needles",
        multiple=1,
        rows=((P(),), (K(),)),
        round_rows=((P(),), (P(),)),
    ),
    "twisted_rib": StitchPattern(
        id="twisted_rib",
        name_key="stitch.twisted_rib",
        technique="needles",
        multiple=2,
        rows=((_op(StitchKind.K1TBL), P()), (K(), _op(StitchKind.P1TBL))),
        round_rows=((_op(StitchKind.K1TBL), P()),),
        # ASUNCION: el elastico retorcido cierra el ancho como un elastico 1x1
        # (unos 20 % mas de pts por 10 cm que el jersey).
        gauge_factor=(1.2, 1.0),
        notes_key="stitch.note.twisted_rib",
    ),
    "broken_rib": StitchPattern(
        id="broken_rib",
        name_key="stitch.broken_rib",
        technique="needles",
        multiple=2,
        rows=((K(2),), (K(), P())),
        round_rows=_in_the_round(((K(2),), (K(), P()))),
        gauge_factor=(1.1, 1.0),  # ASUNCION: cierra la mitad que un elastico
    ),
    "basketweave": StitchPattern(
        id="basketweave",
        name_key="stitch.basketweave",
        technique="needles",
        multiple=8,
        rows=_BASKETWEAVE_ROWS,
        round_rows=_in_the_round(_BASKETWEAVE_ROWS),
        gauge_factor=(1.05, 1.1),  # ASUNCION: los reveses juntan un poco
    ),
    "waffle": StitchPattern(
        id="waffle",
        name_key="stitch.waffle",
        technique="needles",
        multiple=3,
        rows=_WAFFLE_ROWS,
        round_rows=_in_the_round(_WAFFLE_ROWS),
        gauge_factor=(1.05, 1.15),  # ASUNCION: textura en relieve, mas hileras
    ),
    "linen": StitchPattern(
        id="linen",
        name_key="stitch.linen",
        technique="needles",
        multiple=2,
        rows=(
            (K(), _op(StitchKind.SL1_WYIF)),
            (P(), _op(StitchKind.SL1_WYIB)),
        ),
        round_rows=((K(), _op(StitchKind.SL1_WYIF)), (_op(StitchKind.SL1_WYIF), K())),
        # ASUNCION: el punto lino es muy denso (cada pt pasado acorta la
        # hilera); muestras publicadas dan ~1,25 x pts y ~1,7 x hileras.
        gauge_factor=(1.25, 1.7),
        notes_key="stitch.note.linen",
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
    "crochet_tr": StitchPattern(
        id="crochet_tr",
        name_key="stitch.crochet_tr",
        technique="crochet",
        multiple=1,
        rows=((Op(StitchKind.TR),),),
        notes_key="stitch.note.crochet",
    ),
    "crochet_ribbing": StitchPattern(
        id="crochet_ribbing",
        name_key="stitch.crochet_ribbing",
        technique="crochet",
        multiple=1,
        rows=((Op(StitchKind.SC_BLO),),),
        notes_key="stitch.note.crochet_ribbing",
    ),
    "granny_stitch": StitchPattern(
        id="granny_stitch",
        name_key="stitch.granny_stitch",
        technique="crochet",
        multiple=3,
        rows=((Op(StitchKind.GRANNY_GROUP),),),
        notes_key="stitch.note.granny_stitch",
    ),
    # Las hileras van y vuelven: leida desde la otra punta, la secuencia
    # "pb, cad, saltar 1" pone el pb en el esp de cadena y salta el pb.
    "crochet_linen": StitchPattern(
        id="crochet_linen",
        name_key="stitch.crochet_linen",
        technique="crochet",
        multiple=2,
        rows=((Op(StitchKind.SC), Op(StitchKind.CH), Op(StitchKind.SKIP)),),
        notes_key="stitch.note.crochet_linen",
    ),
    "v_stitch": StitchPattern(
        id="v_stitch",
        name_key="stitch.v_stitch",
        technique="crochet",
        multiple=3,
        rows=((Op(StitchKind.SKIP), Op(StitchKind.V_STITCH), Op(StitchKind.SKIP)),),
        notes_key="stitch.note.v_stitch",
    ),
    # Abanico: 5 pa en un pt y 1 pb en el centro del abanico anterior. Con las
    # hileras de ida y vuelta, la misma secuencia pone el abanico sobre el pb
    # y el pb sobre el 3.er pa del abanico.
    "shell": StitchPattern(
        id="shell",
        name_key="stitch.shell",
        technique="crochet",
        multiple=6,
        rows=((Op(StitchKind.SHELL), Op(StitchKind.SKIP, times=2), Op(StitchKind.SC), Op(StitchKind.SKIP, times=2)),),
        notes_key="stitch.note.shell",
    ),
    # Red de filet: pa sobre pa y 1 cad sobre cada cadena. Las hileras se
    # alternan porque al girar la cadena queda primero.
    "filet": StitchPattern(
        id="filet",
        name_key="stitch.filet",
        technique="crochet",
        multiple=2,
        rows=(
            (Op(StitchKind.DC), Op(StitchKind.CH), Op(StitchKind.SKIP)),
            (Op(StitchKind.CH), Op(StitchKind.SKIP), Op(StitchKind.DC)),
        ),
        notes_key="stitch.note.filet",
    ),
    "tunisian": StitchPattern(
        id="tunisian",
        name_key="stitch.tunisian",
        technique="crochet",
        multiple=1,
        rows=((Op(StitchKind.TSS),),),
        row_end=(Op(StitchKind.TUNISIAN_RETURN),),
        notes_key="stitch.note.tunisian",
    ),
    # C2C: la unidad es el bloque. Las diagonales las arma
    # engine/garments/c2c.py; esta entrada da el nombre, el grafico y la
    # densidad (bloques por 10 cm).
    "c2c": StitchPattern(
        id="c2c",
        name_key="stitch.c2c",
        technique="crochet",
        multiple=1,
        rows=((Op(StitchKind.C2C_BLOCK),),),
        notes_key="stitch.note.c2c",
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
    StitchPatternName.REVERSE_STOCKINETTE: "reverse_stockinette",
    StitchPatternName.TWISTED_RIB: "twisted_rib",
    StitchPatternName.BROKEN_RIB: "broken_rib",
    StitchPatternName.BASKETWEAVE: "basketweave",
    StitchPatternName.WAFFLE: "waffle",
    StitchPatternName.LINEN: "linen",
    StitchPatternName.CROCHET_TR: "crochet_tr",
    StitchPatternName.CROCHET_RIBBING: "crochet_ribbing",
    StitchPatternName.GRANNY_STITCH: "granny_stitch",
    StitchPatternName.CROCHET_LINEN: "crochet_linen",
    StitchPatternName.V_STITCH: "v_stitch",
    StitchPatternName.SHELL: "shell",
    StitchPatternName.FILET: "filet",
    StitchPatternName.TUNISIAN: "tunisian",
    StitchPatternName.C2C: "c2c",
}

# Nombres que todavia se aproximan (los usa routing para avisar).
APPROXIMATED_NAMES = frozenset(
    name
    for name in _PATTERN_NAME_TO_ID
    if name.value != _PATTERN_NAME_TO_ID[name]
    and name
    not in {
        StitchPatternName.CABLES,
        StitchPatternName.LACE,
        StitchPatternName.OTHER,
    }
)


# Puntos cuya nota explica como se teje (va en la primera hilera del texto).
_ROW_NOTES = {
    "twisted_rib", "linen", "crochet_ribbing", "granny_stitch", "crochet_linen",
    "v_stitch", "shell", "filet", "tunisian",
}


def stitch_row_note(pattern_id: str, default: str) -> str:
    """Nota de la primera hilera de una pieza en `pattern_id`."""
    notes = STITCH_PATTERNS[pattern_id].notes_key
    return notes if pattern_id in _ROW_NOTES and notes else default


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
) -> tuple[Item, ...]:
    """Expande una vuelta del motivo a un ancho de `stitches` puntos.

    Un motivo de varias operaciones (p. ej. elastico 1x1) se devuelve como
    `Repeat` (*1 d, 1 r; rep*), no multiplicando cada operacion: `40 d, 40 r`
    no es un elastico, es otra tela.
    """
    if stitches <= 0:
        raise ValueError("stitches debe ser > 0")
    if stitches % pattern.multiple != 0:
        raise ValueError(f"{pattern.id}: {stitches} no es multiplo de {pattern.multiple}")
    repeats = stitches // pattern.multiple
    base_ops = pattern.ops_for_row(row_number, in_the_round=in_the_round)
    expanded: tuple[Item, ...]
    if len(base_ops) == 1 or repeats == 1:
        expanded = tuple(Op(op.kind, times=op.times * repeats, width=op.width) for op in base_ops)
    else:
        expanded = (Repeat(times=repeats, ops=tuple(base_ops)),)
    expanded += pattern.row_end
    consumed = sum(item.consumes for item in expanded)
    produced = sum(item.produces for item in expanded)
    if consumed != stitches or produced != stitches:
        raise ValueError(
            f"{pattern.id} vuelta {row_number}: consume {consumed}, produce "
            f"{produced}, se esperaban {stitches}"
        )
    return expanded


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
