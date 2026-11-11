"""Paneles de textura para el cuerpo de prendas tejidas en redondo.

La textura que la IA vio en la foto (trenzas, calados, bodoques, nido de
abeja) se teje como un panel centrado en la espalda y en el delantero del
cuerpo, con 2 pts rev de borde. Todos estos motivos consumen y producen los
mismos puntos que ocupan, asi que los conteos de la prenda no cambian y el
simulador verifica igual cada vuelta.

ASUNCION: el panel no agrega puntos para compensar que las trenzas cierran
el tejido (o que el calado lo abre); se advierte que la muestra debe tejerse
sobre el panel. Ver docs/fuentes.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from engine.ir import Item, Op, Repeat
from engine.spec import GarmentSpec, StitchPatternName, Texture
from engine.stitches.catalog import STITCH_PATTERNS, StitchPattern, get_stitch
from engine.stitches.kinds import StitchKind

_BY_TEXTURE: dict[Texture, str] = {
    Texture.CABLES: "cable_2x2_front",
    Texture.CABLED_RIBBING: "cable_2x2_front",
    Texture.LACE: "lace_basic",
    Texture.BOBBLES: "bobbles",
    Texture.HONEYCOMB: "honeycomb",
}
_BY_STITCH: dict[StitchPatternName, str] = {
    StitchPatternName.CABLES: "cable_2x2_front",
    StitchPatternName.LACE: "lace_basic",
    StitchPatternName.BOBBLES: "bobbles",
    StitchPatternName.HONEYCOMB: "honeycomb",
}
_BORDER = 2
_PANEL_SHARE = 0.4  # fraccion del ancho de la espalda/delantero


def texture_motif(spec: GarmentSpec) -> str | None:
    """Motivo del catalogo para la textura de la foto, o None si es lisa."""
    if spec.punto_base in _BY_STITCH:
        return _BY_STITCH[spec.punto_base]
    for observation in spec.texturas:
        if observation.textura in _BY_TEXTURE:
            return _BY_TEXTURE[observation.textura]
    return None


def round_rows(pattern: StitchPattern) -> tuple[tuple[Op, ...], ...]:
    """Vueltas del motivo tejido en redondo (siempre del lado derecho).

    Las hileras pares de la version plana son del reves: en redondo se teje
    el punto contrario (der <-> rev) y en orden inverso.
    """
    if pattern.round_rows is not None:
        return pattern.round_rows
    swap = {StitchKind.KNIT: StitchKind.PURL, StitchKind.PURL: StitchKind.KNIT}
    rows: list[tuple[Op, ...]] = []
    for index, row in enumerate(pattern.rows):
        if index % 2 == 0:
            rows.append(row)
            continue
        if any(op.kind not in swap for op in row):
            raise ValueError(f"{pattern.id}: la hilera {index + 1} no se puede pasar a redondo")
        rows.append(tuple(Op(swap[op.kind], times=op.times) for op in reversed(row)))
    return tuple(rows)


def _merge(ops: Sequence[Op]) -> tuple[Op, ...]:  # junta ops iguales contiguas
    merged: list[Op] = []
    for op in ops:
        if merged and merged[-1].kind is op.kind and op.width is None and merged[-1].width is None:
            merged[-1] = Op(op.kind, times=merged[-1].times + op.times)
        else:
            merged.append(op)
    return tuple(merged)


@dataclass(frozen=True)
class Panel:
    """Panel de un tramo: 2 rev + `repeats` veces la unidad (+ 2 rev)."""

    motif_id: str
    unit_rows: tuple[tuple[Op, ...], ...]  # una unidad del motivo, en redondo
    repeats: int
    cable: bool

    @property
    def rows(self) -> int:
        return len(self.unit_rows)

    @property
    def unit_width(self) -> int:
        return sum(op.consumes for op in self.unit_rows[0])

    @property
    def width(self) -> int:
        return _BORDER + self.repeats * self.unit_width + (0 if self.cable else _BORDER)

    def items(self, row: int) -> tuple[Item, ...]:
        unit = self.unit_rows[(row - 1) % self.rows]
        items: list[Item] = [Op(StitchKind.PURL, times=_BORDER)]
        items.append(Repeat(self.repeats, unit))
        if not self.cable:
            items.append(Op(StitchKind.PURL, times=_BORDER))
        return tuple(items)

    def flat_items(self, row: int) -> tuple[Item, ...]:
        """Hilera plana del panel: las impares son del LD (como en redondo);
        las pares, del LR, se tejen invertidas y con der <-> rev."""
        items = self.items(row)
        if row % 2 == 1:
            return items
        swap = {StitchKind.KNIT: StitchKind.PURL, StitchKind.PURL: StitchKind.KNIT}

        def flip(op: Op) -> Op:
            if op.kind not in swap:
                raise ValueError(f"{self.motif_id}: la hilera {row} tiene {op.kind.value} del reves")
            return Op(swap[op.kind], times=op.times)

        flipped: list[Item] = []
        for item in reversed(items):
            if isinstance(item, Repeat):
                flipped.append(Repeat(item.times, tuple(flip(op) for op in reversed(item.ops))))
            else:
                flipped.append(flip(item))
        return tuple(flipped)

    def chart(self) -> StitchPattern:
        """Una unidad del motivo, para el grafico del documento."""
        return StitchPattern(
            id=f"panel_{self.motif_id}",
            name_key=get_stitch(self.motif_id).name_key,
            technique="needles",
            multiple=self.unit_width,
            rows=self.unit_rows,
            round_rows=self.unit_rows,
            notes_key=get_stitch(self.motif_id).notes_key,
        )


def build_panel(motif_id: str, segment: int) -> Panel | None:
    """Panel para una parte de `segment` pts, o None si no entra.

    Las trenzas llevan 2 rev despues de cada columna (la unidad es columna +
    2 rev); los demas motivos van contiguos entre dos bordes de 2 rev.
    """
    motif = get_stitch(motif_id)
    cable = motif.id.startswith("cable_")
    rows = round_rows(motif)
    unit_rows = tuple(
        _merge([*row, Op(StitchKind.PURL, times=_BORDER)]) if cable else row for row in rows
    )
    unit = motif.multiple + (_BORDER if cable else 0)
    repeats = max(1, round((segment * _PANEL_SHARE - _BORDER) / unit))
    panel = Panel(motif_id, unit_rows, repeats, cable)
    if panel.width > segment - 4:
        return None
    return panel


def compensation(panel: Panel, stitches_per_cm: float, unit_cm: float | None) -> int:
    """Pts a agregar por panel para que mida lo mismo que el jersey.

    El panel de W pts mide (repeticiones x ancho medido + bordes en jersey);
    eso equivale a E pts de jersey. Faltan W - E pts (redondeado a par). Si el
    motivo no cierra el tejido (calados), no se compensa.
    """
    if unit_cm is None:
        return 0
    border = panel.width - panel.repeats * panel.unit_width
    width_cm = panel.repeats * unit_cm + border / stitches_per_cm
    extra = panel.width - width_cm * stitches_per_cm
    if extra <= 0:
        return 0
    return min(2 * round(extra / 2), panel.width // 2)


Stage = Literal["plain", "increase", "compensated", "decrease"]


def _around_panel(left: int, right: int, panel_items: tuple[Item, ...], extra: int, stage: Stage) -> list[Item]:
    """Pts lisos a los lados del panel, con los aumentos o disminuciones que
    compensan su ancho (la mitad de cada lado)."""
    a, b = extra // 2, extra - extra // 2
    if stage == "increase" and extra:
        return [
            Op(StitchKind.KNIT, times=left),
            *([Op(StitchKind.M1L, times=a)] if a else []),
            *panel_items,
            *([Op(StitchKind.M1R, times=b)] if b else []),
            Op(StitchKind.KNIT, times=right),
        ]
    if stage == "compensated":
        return [Op(StitchKind.KNIT, times=left + a), *panel_items, Op(StitchKind.KNIT, times=right + b)]
    if stage == "decrease" and extra:
        return [
            Op(StitchKind.KNIT, times=left - a),
            *([Op(StitchKind.K2TOG, times=a)] if a else []),
            *panel_items,
            *([Op(StitchKind.SSK, times=b)] if b else []),
            Op(StitchKind.KNIT, times=right - b),
        ]
    return [Op(StitchKind.KNIT, times=left), *panel_items, Op(StitchKind.KNIT, times=right)]


def body_round_with_panels(
    division: Sequence[tuple[str, int]],
    panel: Panel,
    row: int,
    *,
    extra: int = 0,
    stage: Stage = "plain",
) -> tuple[Item, ...]:
    """Vuelta del cuerpo: el panel centrado en los dos tramos tejidos mas
    largos (espalda y delantero de la vuelta de separacion); el resto al der.
    `extra`/`stage`: compensacion del ancho del panel (ver `compensation`)."""
    segments = [n for part, n in division if part in {"knit", "cast_on"}]
    largest = sorted(range(len(segments)), key=lambda i: -segments[i])[:2]
    items: list[Item] = []
    for index, length in enumerate(segments):
        if index in largest:
            left = (length - panel.width) // 2
            right = length - left - panel.width
            items.extend(_around_panel(left, right, panel.items(row), extra, stage))
        else:
            items.append(Op(StitchKind.KNIT, times=length))
    merged: list[Item] = []
    for item in items:
        if isinstance(item, Op) and item.times == 0:
            continue
        last = merged[-1] if merged else None
        if (
            isinstance(item, Op) and isinstance(last, Op) and last.kind is item.kind
            and item.kind in {StitchKind.KNIT, StitchKind.PURL}
            and item.width is None and last.width is None
        ):
            merged[-1] = Op(item.kind, times=last.times + item.times)
        else:
            merged.append(item)
    return tuple(merged)


def panel_for(spec: GarmentSpec, division: Sequence[tuple[str, int]]) -> Panel | None:
    motif = texture_motif(spec)
    if motif is None or motif not in STITCH_PATTERNS:
        return None
    segments = sorted((n for part, n in division if part == "knit"), reverse=True)
    if len(segments) < 2:
        return None
    return build_panel(motif, segments[1])
