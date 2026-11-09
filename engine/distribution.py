"""Reparto determinista de aumentos y disminuciones.

Reglas documentadas:
- Los grupos de puntos entre aumentos difieren como maximo en 1.
- El reparto es simetrico respecto del centro de la vuelta cuando la
  cantidad de grupos lo permite.
- No se redondea "a ojo": cada decision queda en estas funciones.
"""

from __future__ import annotations

from engine.ir import Op, Repeat
from engine.rounding import round_half_up
from engine.stitches.kinds import StitchKind


def split_even(total: int, parts: int) -> list[int]:
    """Divide `total` en `parts` grupos lo mas parejos posible.

    El resto se reparte desde el centro hacia afuera, para que el resultado
    sea simetrico. Ejemplo: split_even(10, 4) -> [2, 3, 3, 2].
    """
    if parts < 1:
        raise ValueError("parts debe ser >= 1")
    if total < 0:
        raise ValueError("total no puede ser negativo")
    base, rest = divmod(total, parts)
    groups = [base] * parts
    if rest == 0:
        return groups
    center = parts // 2
    if parts % 2 == 1:
        # Cantidad impar de grupos: el centro puede recibir un extra.
        if rest % 2 == 1:
            groups[center] += 1
            rest -= 1
        offset = 1
        while rest > 0 and center - offset >= 0:
            groups[center - offset] += 1
            groups[center + offset] += 1
            rest -= 2
            offset += 1
    else:
        # Cantidad par: los extras se reparten en pares simetricos.
        offset = 0
        while rest >= 2 and center - 1 - offset >= 0:
            groups[center - 1 - offset] += 1
            groups[center + offset] += 1
            rest -= 2
            offset += 1
        if rest > 0:
            # Resto impar con cantidad par de grupos: no puede ser simetrico.
            # Se agrega a un grupo base lo mas cerca posible del centro.
            candidates = [
                index for index, value in enumerate(groups) if value == base
            ]
            chosen = min(
                candidates, key=lambda index: (abs(index - (center - 0.5)), index)
            )
            groups[chosen] += 1
    return groups


def even_positions(total: int, count: int) -> list[int]:
    """Posiciones (1..total) donde practicar `count` aumentos repartidos."""
    if count < 0:
        raise ValueError("count no puede ser negativo")
    if count == 0:
        return []
    if count > total:
        raise ValueError(f"no se pueden repartir {count} aumentos en {total} puntos")
    return [
        round_half_up((index + 0.5) * total / count) for index in range(count)
    ]


def _increase_kind(index: int, count: int) -> StitchKind:
    """M1L en la mitad izquierda y M1R en la derecha (simetria)."""
    return StitchKind.M1L if index < (count + 1) // 2 else StitchKind.M1R


def increase_evenly(
    stitches: int, increases: int, *, centered: bool = True
) -> tuple[list[Op], int]:
    """Aumenta `increases` puntos repartidos en una vuelta de `stitches`.

    Devuelve (ops, nuevo_conteo). Los aumentos M1L/M1R no consumen puntos.
    """
    if increases < 0:
        raise ValueError("increases no puede ser negativo")
    if increases == 0:
        return ([Op(StitchKind.KNIT, times=stitches)] if stitches else []), stitches
    if stitches <= 0:
        raise ValueError("se necesitan puntos para aumentar")
    if centered:
        positions = even_positions(stitches, increases)
    else:
        groups = split_even(stitches, increases)
        positions = []
        acc = 0
        for group in groups:
            acc += group
            positions.append(acc)
    ops: list[Op] = []
    previous = 0
    for index, position in enumerate(positions):
        run = position - previous
        if run > 0:
            ops.append(Op(StitchKind.KNIT, times=run))
        ops.append(Op(_increase_kind(index, increases)))
        previous = position
    if previous < stitches:
        ops.append(Op(StitchKind.KNIT, times=stitches - previous))
    return ops, stitches + increases


def decrease_evenly(
    stitches: int,
    decreases: int,
    kind: StitchKind = StitchKind.K2TOG,
    *,
    center_single: bool = True,
) -> tuple[list[Op], int]:
    """Disminuye `decreases` puntos repartidos en una vuelta de `stitches`.

    Cada disminucion consume 2 puntos y produce 1. Se intercalan grupos de
    derechos parejos. Devuelve (ops, nuevo_conteo).
    """
    if kind not in {StitchKind.K2TOG, StitchKind.SSK, StitchKind.P2TOG, StitchKind.SSP}:
        raise ValueError(f"tipo de disminucion no soportado: {kind}")
    if decreases < 0:
        raise ValueError("decreases no puede ser negativo")
    if decreases == 0:
        return ([Op(StitchKind.KNIT, times=stitches)] if stitches else []), stitches
    if decreases * 2 > stitches:
        raise ValueError(
            f"no se pueden hacer {decreases} disminuciones en {stitches} puntos"
        )
    remaining_knits = stitches - 2 * decreases
    if decreases == 1 and center_single:
        left = remaining_knits // 2
        right = remaining_knits - left
        ops: list[Op] = []
        if left:
            ops.append(Op(StitchKind.KNIT, times=left))
        ops.append(Op(kind))
        if right:
            ops.append(Op(StitchKind.KNIT, times=right))
        return ops, stitches - decreases
    groups = split_even(remaining_knits, decreases)
    ops = []
    for group in groups:
        if group:
            ops.append(Op(StitchKind.KNIT, times=group))
        ops.append(Op(kind))
    return ops, stitches - decreases


def paired_decreases(
    stitches: int, left: int, right: int
) -> tuple[list[Op], int]:
    """Disminuciones en ambos bordes (forma de manga encajada, sisa, etc.).

    `left` y `right` son la cantidad de disminuciones de cada lado; se
    intercalan con derechos. Cada lado usa SSK al inicio y K2TOG al final.
    """
    if left < 0 or right < 0:
        raise ValueError("las disminuciones no pueden ser negativas")
    total = left + right
    edges = (1 if left else 0) + (1 if right else 0)
    if total * 2 + edges > stitches:
        raise ValueError(f"demasiadas disminuciones ({total}) para {stitches} puntos")
    middle = stitches - 2 * total - edges
    ops: list[Op] = []
    if left:
        ops.append(Op(StitchKind.KNIT))
        ops.append(Op(StitchKind.SSK, times=left))
    if middle:
        ops.append(Op(StitchKind.KNIT, times=middle))
    if right:
        ops.append(Op(StitchKind.K2TOG, times=right))
        ops.append(Op(StitchKind.KNIT))
    return ops, stitches - total


def repeat_ops(times: int, ops: list[Op]) -> Repeat:
    return Repeat(times=times, ops=tuple(ops))
