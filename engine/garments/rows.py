"""Acumulador de hileras planas: LD en hileras impares, LR en pares.

La hilera 1 es el montaje. Lo comparten las prendas en piezas (manga
encajada, hombro caido, cardigan, chaleco) para que el jersey plano tenga
siempre el reves al reves.
"""

from __future__ import annotations

from engine.distribution import paired_decreases
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
    """Acumula hileras planas alternando LD (impares) y LR (pares)."""

    def __init__(self, start: int, first_number: int = 1) -> None:
        self.current = start
        self.number = first_number
        self.steps: list[Step] = []

    @property
    def right_side(self) -> bool:
        return self.number % 2 == 1

    def add(self, items: tuple[Item, ...] | list[Op], note: str | None = None) -> None:
        step = build_step(self.number, self.current, items, note_key=note)
        self.steps.append(step)
        self.current = step.stitch_count_end
        self.number += 1

    def plain(self, note: str | None = None) -> None:
        kind = StitchKind.KNIT if self.right_side else StitchKind.PURL
        self.add((Op(kind, times=self.current),), note)

    def bind_off_start(self, count: int, note: str | None = None) -> None:
        kind = StitchKind.KNIT if self.right_side else StitchKind.PURL
        self.add((Op(StitchKind.BIND_OFF, times=count), Op(kind, times=self.current - count)), note)

    def decrease_edges(self, note: str | None = None) -> None:
        ops, _ = paired_decreases(self.current, 1, 1)
        self.add(ops, note)

    def increase_edges(self, note: str | None = None) -> None:
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




def rib_rows(rows: FlatRows, pattern: StitchPattern, count: int, note: str | None) -> None:
    for index in range(count):
        rows.add(expand_row(pattern, rows.current, index + 1), note if index == 0 else None)
