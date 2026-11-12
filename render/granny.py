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
from render.draw import STROKE, TEXT_SOFT, _f, caption, label, svg_document, title_block

WIDTH, HEIGHT = 900.0, 760.0

# Nombres de color frecuentes (es/en) -> tono de muestra. Lo desconocido usa
# una escala neutra; el texto siempre nombra el color.
_NAMED = {
    "crema": "#efe6d2", "cream": "#efe6d2", "blanco": "#f7f5f0", "white": "#f7f5f0",
    "beige": "#d9c7a7", "verde": "#6fbf9f", "green": "#6fbf9f", "rosa": "#cf9182",
    "pink": "#cf9182", "gris": "#a9adb0", "grey": "#a9adb0", "gray": "#a9adb0",
    "azul": "#6f8fbf", "blue": "#6f8fbf", "rojo": "#c0504d", "red": "#c0504d",
    "amarillo": "#e8c95a", "yellow": "#e8c95a", "naranja": "#e39252", "orange": "#e39252",
    "violeta": "#9a7cc0", "lila": "#b9a2d6", "purple": "#9a7cc0", "negro": "#3b3b3b",
    "black": "#3b3b3b", "marron": "#8a6247", "marrón": "#8a6247", "brown": "#8a6247",
    "celeste": "#9cc9e3", "mostaza": "#c9a13b", "terracota": "#b8653f",
}
_NEUTRAL = ["#efe6d2", "#d9c7a7", "#c4ad8a", "#a88f6d"]


def _hex(name: str, index: int) -> str:
    """Tono del color nombrado; tambien "verde salvia" o "sage_green" (por
    la palabra conocida que aparezca)."""
    key = name.strip().lower()
    if key in _NAMED:
        return _NAMED[key]
    for word in key.replace("_", " ").replace("-", " ").split():
        if word in _NAMED:
            return _NAMED[word]
    return _NEUTRAL[index % len(_NEUTRAL)]


def render_granny_svg(pattern: Pattern, lang: str) -> str:
    section = pattern.sections[0]
    rounds = len(section.steps)
    colors = list(pattern.materials.colors) or [""]
    side_cm = next((m.value_cm for m in pattern.measurements if m.key == "width"), 20.0)
    size = 420.0
    x0, y0 = (WIDTH - size) / 2, 118.0
    steps = section.steps
    fills = [_hex(colors[n % len(colors)], n) for n in range(rounds)]
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
