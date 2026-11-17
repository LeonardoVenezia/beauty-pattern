"""Estilos de manga (globo, campana, casquillo) y repartos de una vuelta.

La manga recta de cada familia no cambia; estos helpers arman las otras
formas con las mismas piezas de la IR, asi el simulador las verifica igual:

- globo (`puff`): despues de levantar o del puno, una vuelta reparte aumentos
  (ASUNCION: 40 % mas de ancho, como las mangas globo publicadas, 30-50 %) y
  al final se frunce con disminuciones repartidas hacia el puno o la copa;
- campana (`bell`): se abre hacia el borde (ASUNCION: borde = 1,5 x el
  contorno de brazo) con un borde de santa clara que no cierra;
- casquillo (`cap`): manga muy corta, solo la tira (o la copa en la manga
  encajada).
"""

from __future__ import annotations

from engine.distribution import regular_rows
from engine.ir import Item, Op, Repeat, Step, build_step
from engine.rounding import round_half_up
from engine.stitches.kinds import StitchKind

PUFF_FACTOR = 1.4
BELL_FACTOR = 1.5
CAP_BAND_CM = 2.0


def puff_width(stitches: int, multiple: int = 2) -> int:
    """Ancho de la parte fruncida: 40 % mas, como mucho el doble."""
    wide = round_half_up(stitches * PUFF_FACTOR / multiple) * multiple
    return min(2 * stitches, max(stitches + multiple, wide))


def bell_width(stitches: int, multiple: int = 4) -> int:
    return max(stitches + multiple, round_half_up(stitches * BELL_FACTOR / multiple) * multiple)


def spread_increases(stitches: int, count: int, knit: StitchKind = StitchKind.KNIT) -> tuple[Item, ...]:
    """`count` aumentos repartidos en dos grupos parejos: (5 der, m1) 4 veces,
    (4 der, m1) 10 veces. Requiere count <= stitches."""
    if count <= 0:
        return (Op(knit, times=stitches),)
    if count > stitches:
        raise ValueError(f"no entran {count} aumentos en {stitches} pts")
    small, larger = divmod(stitches, count)
    groups = [(small + 1, larger), (small, count - larger)]
    return tuple(
        Repeat(times=n, ops=(Op(knit, times=width), Op(StitchKind.M1L))) for width, n in groups if n
    )


def spread_decreases(stitches: int, count: int, knit: StitchKind = StitchKind.KNIT) -> tuple[Item, ...]:
    """`count` disminuciones (2 juntos) repartidas en dos grupos parejos."""
    if count <= 0:
        return (Op(knit, times=stitches),)
    if 2 * count > stitches:
        raise ValueError(f"no entran {count} disminuciones en {stitches} pts")
    small, larger = divmod(stitches - 2 * count, count)
    groups = [(small + 1, larger), (small, count - larger)]
    return tuple(
        Repeat(
            times=n,
            ops=((Op(knit, times=width),) if width else ()) + (Op(StitchKind.K2TOG),),
        )
        for width, n in groups
        if n
    )


def gather_rounds(stitches: int, target: int) -> list[int]:
    """Disminuciones por vuelta para fruncir de `stitches` a `target`: cada
    vuelta quita como mucho la mitad de lo que hay."""
    counts: list[int] = []
    current = stitches
    while current > target:
        count = min(current - target, current // 2)
        counts.append(count)
        current -= count
    return counts


def puff_round_sleeve(start: int, rows: int, cuff: int) -> list[Step]:
    """Manga globo en redondo, de arriba hacia abajo: levantar, aumentar
    repartido, tejer y fruncir hacia el puno en las ultimas vueltas."""
    wide = puff_width(start)
    gathers = gather_rounds(wide, cuff)
    if rows < 3 + len(gathers):
        raise ValueError("manga globo: no hay vueltas para el frunce")
    steps = [build_step(1, start, (Op(StitchKind.KNIT, times=start),), note_key="pattern.note.sleeve_pickup")]
    steps.append(build_step(2, start, spread_increases(start, wide - start), note_key="garments.note.puff_increase"))
    current = wide
    first_gather = rows - len(gathers) + 1
    for number in range(3, first_gather):
        steps.append(build_step(number, current, (Op(StitchKind.KNIT, times=current),)))
    for index, count in enumerate(gathers):
        steps.append(
            build_step(
                first_gather + index,
                current,
                spread_decreases(current, count),
                note_key="garments.note.puff_gather" if index == 0 else None,
            )
        )
        current -= count
    return steps


def bell_round_sleeve(start: int, rows: int, hem: int) -> list[Step]:
    """Manga campana en redondo: aumentos de a 2 bajo el brazo hasta el borde."""
    incs = (hem - start) // 2
    if incs > rows - 1 or hem - start != 2 * incs:
        raise ValueError("manga campana: no entran los aumentos")
    at = {r + 1 for r in regular_rows(rows - 1, incs)} if incs else set()
    steps: list[Step] = []
    current = start
    for number in range(1, rows + 1):
        if number in at:
            items: tuple[Item, ...] = (
                Op(StitchKind.KNIT),
                Op(StitchKind.M1L),
                Op(StitchKind.KNIT, times=current - 2),
                Op(StitchKind.M1R),
                Op(StitchKind.KNIT),
            )
            steps.append(build_step(number, current, items, note_key="garments.note.bell_increase"))
            current += 2
        else:
            note = "pattern.note.sleeve_pickup" if number == 1 else None
            steps.append(build_step(number, current, (Op(StitchKind.KNIT, times=current),), note_key=note))
    return steps


def cap_round_sleeve(start: int) -> tuple[list[Step], int]:
    """Manga casquillo en redondo: una vuelta y, si hace falta, una
    disminucion para que la tira de elastico 2x2 entre justa."""
    steps = [build_step(1, start, (Op(StitchKind.KNIT, times=start),), note_key="pattern.note.sleeve_pickup")]
    current = start
    if current % 4:
        items = (
            Op(StitchKind.KNIT),
            Op(StitchKind.SSK),
            Op(StitchKind.KNIT, times=current - 6),
            Op(StitchKind.K2TOG),
            Op(StitchKind.KNIT),
        )
        steps.append(build_step(2, current, items, note_key="pattern.note.decrease_sleeve"))
        current -= 2
    return steps, current
