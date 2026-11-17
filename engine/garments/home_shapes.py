"""Formas basicas de las piezas del hogar: circulo, ovalo, rectangulo y tubo.

Cada funcion devuelve vueltas o hileras de la IR (`Step`) ya construidas con
`build_step`, asi que una forma que no cierra la cuenta falla aca y nunca
llega al simulador. Las convenciones (aumentos por vuelta, aumentos
escalonados, punto bobo) estan en docs/fuentes.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import pi

from engine.distribution import split_even
from engine.ir import Item, Op, Repeat, Step, build_step
from engine.stitches.kinds import StitchKind

# Agujas: un circulo plano en jersey crece de a 8 pts (8 gajos), como el
# circulo de los juguetes (engine/garments/toy.py).
KNIT_SECTORS = 8


def circle_increase(stitches_per_cm: float, rows_per_cm: float) -> int:
    """Aumentos por vuelta de un circulo plano de crochet: 2 pi x alto de
    vuelta x pts/cm (6 en pb, 8 en mpa, 12 en pa)."""
    return max(6, min(12, round(2 * pi * stitches_per_cm / rows_per_cm)))


def spread(start: int, end: int, units: int, sectors: int) -> list[int]:
    """Conteo al final de cada una de `units` vueltas para ir de `start` a
    `end` en cambios de `sectors` pts, repartidos parejo en el tramo."""
    changes = abs(end - start) // sectors
    if changes > units:
        raise ValueError(f"{changes} cambios no entran en {units} vueltas")
    sign = 1 if end >= start else -1
    counts: list[int] = []
    current = start

    def done(index: int) -> int:
        return (2 * index * changes + units) // (2 * units)

    for index in range(units):
        if done(index + 1) > done(index):
            current += sign * sectors
        counts.append(current)
    return counts


def change_items(
    count: int,
    changes: int,
    plain: StitchKind,
    change: StitchKind,
    *,
    offset: bool = False,
) -> list[Item]:
    """`changes` aumentos (consumen 1 pt) o disminuciones (consumen 2)
    repartidos parejo en una vuelta de `count` pts.

    `offset`: la vuelta empieza con medio tramo, asi los aumentos de una
    vuelta caen entre los de la anterior (el circulo no se vuelve poligono).
    """
    if changes == 0:
        return [Op(plain, times=count)]
    width = 2 if change in {StitchKind.CROCHET_DEC, StitchKind.K2TOG} else 1
    rest = count - width * changes
    if rest < 0:
        raise ValueError(f"no entran {changes} cambios en {count} pts")
    groups = split_even(rest, changes)
    if len(set(groups)) == 1:
        gap = groups[0]
        if offset and gap >= 2:
            half = gap // 2
            items: list[Item] = [Op(plain, times=half)]
            if changes > 1:
                items.append(Repeat(changes - 1, (Op(change), Op(plain, times=gap))))
            items += [Op(change), Op(plain, times=gap - half)]
            return items
        unit = ((Op(plain, times=gap),) if gap else ()) + (Op(change),)
        return [Repeat(changes, unit)]
    ops: list[Item] = []
    for gap in groups:
        if gap:
            ops.append(Op(plain, times=gap))
        ops.append(Op(change))
    return ops


def compress(kinds: Sequence[StitchKind]) -> list[Item]:
    """Lista de puntos sueltos -> tramos ("3 pb, aum, 3 pb"), con los pares
    que se repiten seguidos agrupados ("(aum, 2 pb) 3 veces")."""
    runs = _runs(kinds)
    items: list[Item] = []
    index = 0
    while index < len(runs):
        times = 1
        while index + 1 < len(runs) and runs[index : index + 2] == runs[index + 2 * times : index + 2 * times + 2]:
            times += 1
        if times >= 2:
            items.append(Repeat(times, (runs[index], runs[index + 1])))
            index += 2 * times
        else:
            items.append(runs[index])
            index += 1
    return items


def _runs(kinds: Sequence[StitchKind]) -> list[Op]:
    ops: list[Op] = []
    run_kind: StitchKind | None = None
    run = 0
    for kind in kinds:
        if kind is run_kind:
            run += 1
            continue
        if run_kind is not None:
            ops.append(Op(run_kind, times=run))
        run_kind, run = kind, 1
    if run_kind is not None:
        ops.append(Op(run_kind, times=run))
    return ops


# ---------------------------------------------------------------------------
# Circulo.
# ---------------------------------------------------------------------------


def crochet_circle(
    kind: StitchKind, inc: int, rounds: int, *, note: str = "home.note.circle"
) -> list[Step]:
    """Circulo plano de crochet: anillo de `inc` pts y `inc` aumentos por
    vuelta; la vuelta r tiene r x inc pts. Los aumentos se escalonan en las
    vueltas pares (convencion para que quede redondo y no hexagonal)."""
    steps = [build_step(1, 0, (Op(StitchKind.RING, width=inc),))]
    count = inc
    for number in range(2, rounds + 1):
        items = change_items(count, inc, kind, StitchKind.CROCHET_INC, offset=number % 2 == 0)
        steps.append(build_step(number, count, items, note_key=note if number == 2 else None))
        count += inc
    return steps


def knit_circle(final: int, rounds: int, *, edge: int = 0) -> list[Step]:
    """Circulo plano en jersey en redondo desde el centro: montar 8 pts, 8
    aumentos (kfb) en las vueltas que tocan, repartidas parejo, hasta `final`;
    `edge` vueltas finales de punto bobo en redondo (rev, der) para que el
    borde no se enrolle. `rounds` incluye el montaje."""
    sectors = KNIT_SECTORS
    counts = spread(sectors, final, rounds - 1 - edge, sectors)
    steps = [
        build_step(1, 0, (Op(StitchKind.CAST_ON, times=sectors),), note_key="home.note.knit_center")
    ]
    count = sectors
    for index, target in enumerate(counts):
        items = change_items(count, target - count, StitchKind.KNIT, StitchKind.KFB)
        steps.append(build_step(index + 2, count, items))
        count = target
    for index in range(edge):
        kind = StitchKind.PURL if index % 2 == 0 else StitchKind.KNIT
        note = "home.note.garter_edge_round" if index == 0 else None
        steps.append(build_step(len(steps) + 1, count, (Op(kind, times=count),), note_key=note))
    return steps


# ---------------------------------------------------------------------------
# Ovalo de crochet: cadena base trabajada por los dos lados.
# ---------------------------------------------------------------------------


def _end_kinds(stitches: int, incs: int, kind: StitchKind) -> list[StitchKind]:
    """Un extremo del ovalo: `incs` aumentos centrados en tramos parejos."""
    out: list[StitchKind] = []
    for gap in split_even(stitches - incs, incs):
        out += [kind] * (gap // 2) + [StitchKind.CROCHET_INC] + [kind] * (gap - gap // 2)
    return out


def _produced(kinds: Sequence[StitchKind]) -> int:
    return sum(2 if kind is StitchKind.CROCHET_INC else 1 for kind in kinds)


def crochet_oval(
    kind: StitchKind, straight: int, end_incs: int, rounds: int
) -> tuple[list[Step], int, int]:
    """Ovalo: cadena de `straight` + 2 pts y vueltas alrededor.

    Vuelta 1 (paso 2): `c - 1` pts por un lado (uno en cada cadena), aum en
    la ultima cadena y el resto por el otro lado de la cadena, de modo que
    cada cadena de un extremo recibe `end_incs` pts (3 en pb, 4 en mpa, 6 en
    pa) y cada cadena del medio uno de cada lado. Despues, los lados rectos
    (`straight` pts) se tejen sin cambios y cada extremo (medio circulo) suma
    `end_incs` aumentos por vuelta, como medio circulo plano. `rounds` cuenta
    las vueltas de puntos (sin la cadena). Devuelve (pasos, pts del extremo 1
    al comienzo de la ultima vuelta, pts de cada extremo)."""
    chain = straight + 2
    k = end_incs
    steps = [build_step(1, 0, (Op(StitchKind.CH, times=chain),), note_key="home.note.oval_chain")]
    other = (k - 2) + straight + (k - 1)
    first: list[Item] = [
        Op(kind, times=chain - 1),
        Op(StitchKind.CROCHET_INC),
        Op(StitchKind.CROCHET_EDGE, times=other),
    ]
    steps.append(
        build_step(
            2,
            chain,
            first,
            note_key="home.note.oval_first",
            note_params=(("n", str(other)), ("k", str(k))),
        )
    )
    # Extremo 1 partido por el comienzo de la vuelta: `head` pts al principio
    # y `tail` al final; extremo 2 entero en el medio.
    head, tail, end = 1, k - 1, k
    count = 2 * straight + 2 * k
    for number in range(3, rounds + 2):
        one = _end_kinds(head + tail, end_incs, kind)
        two = _end_kinds(end, end_incs, kind)
        sequence = one[:head] + [kind] * straight + two + [kind] * straight + one[head:]
        step = build_step(
            number, count, compress(sequence), note_key="home.note.oval_round" if number == 3 else None
        )
        steps.append(step)
        head, tail, end = _produced(one[:head]), _produced(one[head:]), _produced(two)
        count = step.stitch_count_end
    return steps, head, end


# ---------------------------------------------------------------------------
# Hileras y vueltas rectas.
# ---------------------------------------------------------------------------


def plain_rounds(
    first_number: int, count: int, rounds: int, kind: StitchKind, *, note: str | None = None
) -> list[Step]:
    return [
        build_step(first_number + i, count, (Op(kind, times=count),), note_key=note if i == 0 else None)
        for i in range(rounds)
    ]


def handle_round(
    number: int,
    count: int,
    width: int,
    first_center: int,
    kind: StitchKind,
    *,
    craft: str,
) -> tuple[Step, Step]:
    """Dos aberturas opuestas de `width` pts (asas de canasto): la vuelta que
    las abre (crochet: cadenas y saltar; agujas: cerrar pts) y la que las
    cierra (crochet: pts sobre las cadenas; agujas: montar pts)."""
    if count % 2 or width >= count // 2 - 2:
        raise ValueError("asas: la vuelta es chica para las aberturas")
    half = count // 2
    start = min((first_center - width // 2) % half, half - width)
    gap = count // 2 - width
    tail = count - start - 2 * width - gap
    if craft == "crochet":
        hole: tuple[Op, ...] = (Op(StitchKind.CH, times=width), Op(StitchKind.SKIP, times=width))
        refill: tuple[Op, ...] = (Op(kind, times=width),)
    else:
        hole = (Op(StitchKind.BIND_OFF, times=width),)
        refill = (Op(StitchKind.CAST_ON, times=width),)
    open_items: list[Item] = []
    close_items: list[Item] = []
    for seg, part in ((start, 0), (gap, 1), (tail, 2)):
        if seg:
            open_items.append(Op(kind, times=seg))
            close_items.append(Op(kind, times=seg))
        if part < 2:
            open_items.extend(hole)
            close_items.extend(refill)
    opened = build_step(number, count, open_items, note_key="home.note.handles_open", note_params=(("n", str(width)),))
    middle = opened.stitch_count_end
    closed = build_step(number + 1, middle, close_items, note_key="home.note.handles_close")
    return opened, closed
