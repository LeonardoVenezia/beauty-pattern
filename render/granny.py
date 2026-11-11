"""Diagrama del granny square: una franja por vuelta, con su color y sus grupos.

Se dibuja desde la IR: cantidad de vueltas y grupos por lado salen de las
vueltas verificadas. Los colores siguen la paleta (A, B, C...) por vuelta.
"""

from __future__ import annotations

from engine.i18n import t
from engine.ir import Pattern
from render.draw import STROKE, TEXT, TEXT_SOFT, _f, caption, label, svg_document, title_block

WIDTH, HEIGHT = 900.0, 720.0

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
    x0, y0 = (WIDTH - size) / 2, 130.0
    band = size / 2 / (rounds + 0.6)
    parts: list[str] = []
    for n in range(rounds, 0, -1):
        inset = (rounds - n) * band
        x, y, w = x0 + inset, y0 + inset, size - 2 * inset
        color = _hex(colors[(n - 1) % len(colors)], n - 1)
        parts.append(
            f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(w)}" '
            f'fill="{color}" stroke="{STROKE}" stroke-width="0.8"/>'
        )
        # Grupos de 3 pa: n + 1 por lado (2 de esquina + n - 1 laterales).
        per_side = n + 1
        mid = band / 2
        for k in range(per_side):
            t_pos = (k + 0.5) / per_side
            for sx, sy in (
                (x + t_pos * w, y + mid),
                (x + t_pos * w, y + w - mid),
                (x + mid, y + t_pos * w),
                (x + w - mid, y + t_pos * w),
            ):
                parts.append(f'<circle cx="{_f(sx)}" cy="{_f(sy)}" r="{_f(min(3.2, band / 5))}" fill="{STROKE}" opacity="0.55"/>')
        if n <= 9 or n == rounds:
            parts.append(label(x + band * 0.5, y + band * 0.5 + 4, str(n), size=10, color=TEXT))
    centre = x0 + size / 2
    parts.append(f'<circle cx="{_f(centre)}" cy="{_f(y0 + size / 2)}" r="{_f(band * 0.35)}" fill="#ffffff" stroke="{STROKE}"/>')
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
        parts.append(label(centre, HEIGHT - 52, legend, size=11, color=TEXT_SOFT))
    title = t(pattern.meta.title_key, lang)
    head = title_block(WIDTH, 42, title, t("schematic.granny_note", lang, n=rounds))
    tail = [caption(WIDTH, HEIGHT - 20, t("schematic.caption", lang))]
    return svg_document(WIDTH, HEIGHT, title, t("pattern.schematic", lang), head + parts + tail)
