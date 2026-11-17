"""Crochet esquina a esquina (C2C): rectangulos tejidos en diagonales de bloques.

Cada bloque es 3 cad + 3 pa. Se empieza en una esquina con un bloque y cada
diagonal suma un bloque por cada borde que todavia crece; cuando un borde
llega a su medida deja de crecer (en ese borde se disminuye) y al final las
dos disminuyen hasta cerrar en la esquina opuesta.

Geometria (W bloques de ancho, H de alto): las diagonales impares empiezan en
el borde de abajo y las pares en el borde izquierdo. El borde de abajo crece
durante las primeras W diagonales y el izquierdo durante las primeras H. La
diagonal r tiene min(r, W, H, W + H - r) bloques: el simulador verifica cada
conteo y los tests, que coincida con esa formula.

ASUNCION: un bloque mide de lado lo que 3,3 pb (engine/gauge.py, "c2c").
"""

from __future__ import annotations

from engine.colorwork import BG, FG, ColorworkChart, palette
from engine.ir import Item, Op, Section, SectionTarget, Step, build_step
from engine.spec import GarmentSpec
from engine.stitches.kinds import StitchKind


def diagonal_blocks(row: int, width: int, height: int) -> int:
    """Bloques de la diagonal `row` (1..W+H-1) de un rectangulo W x H."""
    return min(row, width, height, width + height - row)


def c2c_steps(width: int, height: int) -> tuple[Step, ...]:
    if width < 1 or height < 1:
        raise ValueError("el C2C necesita al menos 1 bloque por lado")
    steps: list[Step] = []
    current = 0
    for row in range(1, width + height):
        bottom_grows = row <= width
        side_grows = row <= height
        starts_bottom = row % 2 == 1
        start_grows, end_grows = (bottom_grows, side_grows) if starts_bottom else (side_grows, bottom_grows)
        items: list[Item] = [Op(StitchKind.C2C_NEW if start_grows else StitchKind.C2C_SLIDE)]
        worked = current - (0 if end_grows else 1)
        if worked > 0:
            items.append(Op(StitchKind.C2C_BLOCK, times=worked))
        if not end_grows and current > 0:
            items.append(Op(StitchKind.C2C_TURN))
        if row == 1:
            note = "pattern.note.c2c_start"
        elif row == min(width, height) + 1:
            note = "pattern.note.c2c_decrease" if width == height else "pattern.note.c2c_plateau"
        elif row == max(width, height) + 1 and width != height:
            note = "pattern.note.c2c_decrease"
        else:
            note = None
        step = build_step(row, current, items, note_key=note)
        steps.append(step)
        current = step.stitch_count_end
    return tuple(steps)


def c2c_section(
    section_id: str, name_key: str, width: int, height: int, target_cm: float, tolerance_cm: float = 1.5
) -> Section:
    steps = c2c_steps(width, height)
    return Section(
        id=section_id,
        name_key=name_key,
        mode="flat",
        steps=steps,
        start_stitches=0,
        end_stitches=steps[-1].stitch_count_end,
        target=SectionTarget(
            measurement_key=f"{section_id}_length", target_cm=target_cm, tolerance_cm=tolerance_cm, dimension="length"
        ),
        # El largo de la pieza son los H bloques del borde, no las diagonales.
        meta={"row_count": height, "c2c_width": width, "c2c_height": height},
        bind_off=True,
        note_keys=("pattern.note.c2c_intro",),
    )


def c2c_chart(spec: GarmentSpec, width: int, height: int) -> ColorworkChart | None:
    """Dibujo de pixeles (un bloque = un pixel) si la foto tiene 2+ colores:
    rombos repetidos con un marco de 1 bloque. Original, por reglas."""
    colors = spec.colorwork.paleta if spec.colorwork else []
    if len(palette(colors)) < 2 or not spec.colorwork or spec.colorwork.colores < 2:
        return None
    if width < 6 or height < 6:
        return None

    def on(r: int, c: int) -> bool:
        if r in (0, height - 1) or c in (0, width - 1):
            return True
        # Rombo de 8 bloques de lado (ASUNCION de diseno, sin fuente).
        x, y = (c - 1) % 8, (r - 1) % 8
        return abs(x - 3.5) + abs(y - 3.5) in (3.0, 4.0)

    rows = tuple("".join(FG if on(r, c) else BG for c in range(width)) for r in range(height))
    return ColorworkChart(number=1, motif="c2c_pixels", rows=rows, background=0, contrast=1)
