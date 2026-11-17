"""Forma del cuerpo hacia el borde: cadera del vestido y linea A.

En las prendas de arriba hacia abajo (raglan, canesu) el cuerpo se ensancha
con 4 aumentos por vuelta en los costados (1 a cada lado de cada costado);
en las de abajo hacia arriba se monta el ancho del borde y se disminuye en los
bordes de cada pieza. Ver `options.hem_circumference_cm`.
"""

from __future__ import annotations

from collections.abc import Sequence

from engine.distribution import regular_rows
from engine.ir import Item, Op, Step, build_step, division_ops
from engine.stitches.kinds import StitchKind


def side_centers(division: Sequence[tuple[str, int]]) -> tuple[int, int]:
    """Pts desde el comienzo de la vuelta hasta el centro de cada axila (los
    costados), en la vuelta del cuerpo."""
    position = 0
    centers: list[int] = []
    for part, count in division:
        if part == "hold":
            continue
        if part == "cast_on":
            centers.append(position + count // 2)
        position += count
    if len(centers) != 2:
        raise ValueError("se esperaban dos axilas")
    return centers[0], centers[1]


def side_increase_round(stitches: int, first: int, second: int) -> tuple[Item, ...]:
    """Vuelta con 1 aumento a cada lado de cada costado (4 en total)."""
    return (
        Op(StitchKind.KNIT, times=first - 1),
        Op(StitchKind.M1R),
        Op(StitchKind.KNIT, times=2),
        Op(StitchKind.M1L),
        Op(StitchKind.KNIT, times=second - first - 2),
        Op(StitchKind.M1R),
        Op(StitchKind.KNIT, times=2),
        Op(StitchKind.M1L),
        Op(StitchKind.KNIT, times=stitches - second - 1),
    )


def flare_rounds(rows: int, increases: int) -> set[int]:
    """Vueltas (2..rows-1) con aumentos de costado, a ritmo regular."""
    if increases <= 0:
        return set()
    usable = rows - 2
    if increases > usable:
        raise ValueError("no entran los aumentos de la falda")
    return {row + 1 for row in regular_rows(usable, increases)}


def flared_round_body(
    division: Sequence[tuple[str, int]], body_before: int, body_sts: int, rows: int, hem_sts: int
) -> list[Step]:
    """Cuerpo en redondo desde la separacion hasta el borde, ensanchando de
    `body_sts` a `hem_sts` (multiplo de 4 de diferencia)."""
    increases = (hem_sts - body_sts) // 4
    at = flare_rounds(rows, increases)
    first, second = side_centers(division)
    steps = [build_step(1, body_before, division_ops(division), note_key="pattern.note.separation")]
    current = body_sts
    done = 0
    for number in range(2, rows + 1):
        if number in at:
            items = side_increase_round(current, first + done, second + 3 * done)
            note = "garments.note.skirt_increase" if done == 0 else None
            steps.append(build_step(number, current, items, note_key=note))
            current += 4
            done += 1
        else:
            steps.append(build_step(number, current, (Op(StitchKind.KNIT, times=current),)))
    if current != hem_sts:
        raise RuntimeError(f"cuerpo: termina con {current}, se esperaban {hem_sts}")
    return steps
