"""Grafico de simbolos del granny square: una franja por vuelta, con su color.

Se dibuja desde la IR: cantidad de vueltas y grupos por lado salen de las
vueltas verificadas. Los colores siguen la paleta (A, B, C...) por vuelta.
"""

from __future__ import annotations

from engine.i18n import t
from engine.ir import Pattern
from engine.stitches.kinds import StitchKind
from render.crochet_chart import draw_rounds
from render.crochet_chart import legend as chart_legend
from render.draw import STROKE, TEXT_SOFT, _f, caption, label, svg_document, swatch, title_block

WIDTH, HEIGHT = 900.0, 760.0

def render_granny_svg(pattern: Pattern, lang: str) -> str:
    section = pattern.sections[0]
    rounds = len(section.steps)
    colors = list(pattern.materials.colors) or [""]
    side_cm = next((m.value_cm for m in pattern.measurements if m.key == "width"), 20.0)
    size = 420.0
    x0, y0 = (WIDTH - size) / 2, 118.0
    steps = section.steps
    fills = [swatch(colors[n % len(colors)], n) for n in range(rounds)]
    parts, used = draw_rounds(
        steps, [StitchKind.DC] * rounds, [True] * rounds, fills, x0 + size / 2, y0 + size / 2, size / 2
    )
    centre = x0 + size / 2
    y_dim = y0 + size + 24
    parts.append(
        f'<line x1="{_f(x0)}" y1="{_f(y_dim)}" x2="{_f(x0 + size)}" y2="{_f(y_dim)}" stroke="{STROKE}"/>'
    )
    for xx in (x0, x0 + size):
        parts.append(f'<line x1="{_f(xx)}" y1="{_f(y_dim - 5)}" x2="{_f(xx)}" y2="{_f(y_dim + 5)}" stroke="{STROKE}"/>')
    unit = t(f"unit.{pattern.params.unidades}", lang)
    shown = side_cm / 2.54 if pattern.params.unidades == "in" else side_cm
    parts.append(label(centre, y_dim + 18, f"{round(shown * 2) / 2:g} {unit}", size=12, weight="700"))
    if pattern.materials.colors:
        legend = "   ".join(
            f"{chr(65 + i)}: {name}" for i, name in enumerate(pattern.materials.colors)
        )
        parts.append(label(centre, y_dim + 36, legend, size=11, color=TEXT_SOFT))
    parts += chart_legend(used, lang, 90, y_dim + 74, WIDTH - 180)
    title = t(pattern.meta.title_key, lang)
    head = title_block(WIDTH, 42, title, t("schematic.granny_note", lang, n=rounds))
    tail = [caption(WIDTH, HEIGHT - 20, t("schematic.caption", lang))]
    return svg_document(WIDTH, HEIGHT, title, t("pattern.schematic", lang), head + parts + tail)
