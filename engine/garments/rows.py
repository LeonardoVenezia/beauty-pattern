"""Acumulador de hileras planas: LD en hileras impares, LR en pares.

La hilera 1 es el montaje. Lo comparten las prendas en piezas (manga
encajada, hombro caido, cardigan, chaleco) para que el jersey plano tenga
siempre el reves al reves.
"""

from __future__ import annotations

from collections.abc import Sequence

from engine.distribution import paired_decreases
from engine.garments.panels import Panel
from engine.ir import Item, Op, Step, build_step
from engine.stitches.catalog import StitchPattern, expand_row, get_stitch
from engine.stitches.kinds import StitchKind


def hem_rib(stitches: int) -> StitchPattern:
    """Elastico que entra justo: 2x2, 1x1 o santa clara si el numero es impar."""
    if stitches % 4 == 0:
        return get_stitch("rib_2x2")
    if stitches % 2 == 0:
        return get_stitch("rib_1x1")
    return get_stitch("garter")


class FlatRows:
    """Acumula hileras planas alternando LD (impares) y LR (pares).

    Con `start_panel` lleva un panel de textura: guarda cuantos pts lisos hay
    a cada lado (vistos del LD) para que el panel no se mueva cuando se
    cierran o disminuyen pts en los bordes (sisa, copa).
    """

    def __init__(self, start: int, first_number: int = 1) -> None:
        self.current = start
        self.number = first_number
        self.steps: list[Step] = []
        self.panel: Panel | None = None
        self.left = 0
        self.right = 0
        self.chart_row = 1
        self.first_chart_row = 1

    @property
    def right_side(self) -> bool:
        return self.number % 2 == 1

    def add(self, items: Sequence[Item], note: str | None = None) -> None:
        kept = [item for item in items if not (isinstance(item, Op) and item.times == 0)]
        step = build_step(self.number, self.current, kept, note_key=note)
        self.steps.append(step)
        self.current = step.stitch_count_end
        self.number += 1
        if self.panel is not None:
            self.chart_row = self.chart_row % self.panel.rows + 1

    def start_panel(self, panel: Panel) -> None:
        self.panel = panel
        self.left = (self.current - panel.width) // 2
        self.right = self.current - panel.width - self.left
        # Las hileras impares del grafico son del LD.
        self.chart_row = 1 if self.right_side else panel.rows
        self.first_chart_row = self.chart_row

    def row(self, *, bind_off: int = 0, decrease: bool = False, note: str | None = None) -> None:
        """Hilera de jersey (con panel si hay): cierre al inicio y/o una
        disminucion en cada borde (solo en hileras del LD)."""
        if decrease and not self.right_side:
            raise ValueError("las disminuciones de borde van en hileras del LD")
        knit = StitchKind.KNIT if self.right_side else StitchKind.PURL
        items: list[Item] = []
        if bind_off:
            items.append(Op(StitchKind.BIND_OFF, times=bind_off))
        if self.panel is None:
            if decrease:
                ops, _ = paired_decreases(self.current - bind_off, 1, 1)
                items.extend(ops)
            else:
                items.append(Op(knit, times=self.current - bind_off))
            self.add(items, note)
            return
        if self.right_side:
            self.left -= bind_off
            if decrease:
                items += [Op(StitchKind.KNIT), Op(StitchKind.SSK)]
            items.append(Op(StitchKind.KNIT, times=self.left - (3 if decrease else 0)))
            items.extend(self.panel.flat_items(self.chart_row))
            items.append(Op(StitchKind.KNIT, times=self.right - (3 if decrease else 0)))
            if decrease:
                items += [Op(StitchKind.K2TOG), Op(StitchKind.KNIT)]
                self.left -= 1
                self.right -= 1
        else:
            self.right -= bind_off
            items.append(Op(StitchKind.PURL, times=self.right))
            items.extend(self.panel.flat_items(self.chart_row))
            items.append(Op(StitchKind.PURL, times=self.left))
        self.add(items, note)

    def plain(self, note: str | None = None) -> None:
        self.row(note=note)

    def bind_off_start(self, count: int, note: str | None = None) -> None:
        self.row(bind_off=count, note=note)

    def decrease_edges(self, note: str | None = None) -> None:
        self.row(decrease=True, note=note)

    def increase_edges(self, note: str | None = None) -> None:
        if self.panel is not None:
            raise ValueError("aumentos de borde con panel no soportados")
        self.add(
            (
                Op(StitchKind.KNIT),
                Op(StitchKind.M1L),
                Op(StitchKind.KNIT, times=self.current - 2),
                Op(StitchKind.M1R),
                Op(StitchKind.KNIT),
            ),
            note,
        )

    def panel_meta(self, start: int, segment: int) -> dict[str, int]:
        if self.panel is None:
            return {}
        return {
            "panel_rows": self.panel.rows,
            "panel_repeats": self.panel.repeats,
            "panel_width": self.panel.width,
            "panel_start": start,
            "panel_segment": segment,
            "panel_first_chart_row": self.first_chart_row,
        }


def rib_rows(rows: FlatRows, pattern: StitchPattern, count: int, note: str | None) -> None:
    for index in range(count):
        rows.add(expand_row(pattern, rows.current, index + 1), note if index == 0 else None)
