"""Graficos de jacquard en SVG.

Cuadros con el color de la paleta y un simbolo por color (para imprimir en
blanco y negro), numeros de vuelta a la derecha de abajo hacia arriba,
numeros de punto abajo de derecha a izquierda, llave con el ancho de la
repeticion y referencias con el nombre de cada color.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from engine.colorwork import ColorworkChart, color_letter, color_name
from engine.i18n import t
from render.draw import swatch

CELL = 22
MARGIN_LEFT = 24
MARGIN_TOP = 50
MIN_WIDTH = 440
FONT = "Helvetica, Arial, sans-serif"
GRID = "#555555"


def _f(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _ink(hex_color: str) -> str:
    """Tinta del simbolo: negra sobre colores claros, blanca sobre oscuros."""
    value = hex_color.lstrip("#")
    try:
        r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return "#111111"
    return "#111111" if 0.299 * r + 0.587 * g + 0.114 * b > 140 else "#ffffff"


def _symbol(index: int, x: float, y: float, size: float, ink: str) -> str:
    """Simbolo del color `index` (A = fondo, sin simbolo)."""
    pad = size * 0.25
    stroke = f'stroke="{ink}" stroke-width="{_f(max(1.2, size / 11))}" stroke-linecap="round"'
    cx, cy = x + size / 2, y + size / 2
    kind = index % 5
    if index == 0:
        return ""
    if kind == 1:  # cruz en X
        return (
            f'<line x1="{_f(x + pad)}" y1="{_f(y + pad)}" x2="{_f(x + size - pad)}" '
            f'y2="{_f(y + size - pad)}" {stroke}/>'
            f'<line x1="{_f(x + size - pad)}" y1="{_f(y + pad)}" x2="{_f(x + pad)}" '
            f'y2="{_f(y + size - pad)}" {stroke}/>'
        )
    if kind == 2:  # punto lleno
        return f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(size * 0.2)}" fill="{ink}"/>'
    if kind == 3:  # triangulo
        return (
            f'<polygon points="{_f(cx)},{_f(y + pad)} {_f(x + size - pad)},{_f(y + size - pad)} '
            f'{_f(x + pad)},{_f(y + size - pad)}" fill="none" {stroke}/>'
        )
    if kind == 4:  # barra
        return (
            f'<line x1="{_f(x + size - pad)}" y1="{_f(y + pad)}" x2="{_f(x + pad)}" '
            f'y2="{_f(y + size - pad)}" {stroke}/>'
        )
    return f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(size * 0.22)}" fill="none" {stroke}/>'


def _text(x: float, y: float, text: str, *, size: float = 10, anchor: str = "start", bold: bool = False) -> str:
    # svglib solo usa la negrita si la familia es "Helvetica-Bold".
    family = 'font-family="Helvetica-Bold, Arial, sans-serif" font-weight="700"' if bold else f'font-family="{FONT}"'
    return (
        f'<text x="{_f(x)}" y="{_f(y)}" text-anchor="{anchor}" {family} '
        f'font-size="{_f(size)}" fill="#222222">{escape(text)}</text>'
    )


def render_colorwork_chart_svg(chart: ColorworkChart, palette: tuple[str, ...], *, lang: str = "es") -> str:
    """Grafico de una guarda de jacquard (una repeticion)."""

    def fill(index: int) -> str:
        return swatch(palette[index], index) if index < len(palette) else "#ffffff"

    grid_w = chart.width * CELL
    grid_h = chart.height * CELL
    used = sorted({chart.background, chart.contrast})
    legend_top = MARGIN_TOP + grid_h + 70
    width = max(MIN_WIDTH, MARGIN_LEFT + grid_w + 60)
    height = legend_top + len(used) * 24 + 30
    name = t(f"colorwork.motif.{chart.motif}", lang)
    title = t("chart.colorwork_title", lang, n=chart.number, name=name)
    repeat = t("chart.colorwork_repeat", lang, w=chart.width)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_f(width)}" height="{_f(height)}" '
        f'viewBox="0 0 {_f(width)} {_f(height)}" role="img" aria-label="{escape(title)}">',
        f"<title>{escape(title)}</title>",
        f'<rect x="0" y="0" width="{_f(width)}" height="{_f(height)}" fill="#ffffff"/>',
        _text(MARGIN_LEFT, 22, title, size=14, bold=True),
        _text(MARGIN_LEFT, 38, repeat, size=10),
    ]
    for row in range(1, chart.height + 1):
        y = MARGIN_TOP + (chart.height - row) * CELL
        for col in range(1, chart.width + 1):
            x = MARGIN_LEFT + (chart.width - col) * CELL
            color = chart.color_at(row, col)
            parts.append(
                f'<rect x="{_f(x)}" y="{_f(y)}" width="{CELL}" height="{CELL}" '
                f'fill="{fill(color)}" stroke="{GRID}" stroke-width="0.6"/>'
            )
            parts.append(_symbol(color, x, y, CELL, _ink(fill(color))))
        parts.append(_text(MARGIN_LEFT + grid_w + 6, y + CELL / 2 + 3.5, str(row), anchor="start"))
    parts.append(
        f'<rect x="{MARGIN_LEFT}" y="{MARGIN_TOP}" width="{_f(grid_w)}" height="{_f(grid_h)}" '
        'fill="none" stroke="#c0392b" stroke-width="2"/>'
    )
    numbers_y = MARGIN_TOP + grid_h + 12
    for col in range(1, chart.width + 1):
        x = MARGIN_LEFT + (chart.width - col) * CELL + CELL / 2
        parts.append(_text(x, numbers_y, str(col), size=8.5, anchor="middle"))
    # Llave de la repeticion.
    by = numbers_y + 8
    left, right = MARGIN_LEFT + 1, MARGIN_LEFT + grid_w - 1
    parts.append(
        f'<path d="M{_f(left)},{_f(by)} v5 H{_f(right)} v-5 M{_f((left + right) / 2)},{_f(by + 5)} v4" '
        'fill="none" stroke="#c0392b" stroke-width="1.4"/>'
    )
    parts.append(_text((left + right) / 2, by + 21, repeat, size=9.5, anchor="middle"))
    parts.append(_text(MARGIN_LEFT, legend_top - 6, t("chart.legend", lang), size=11, bold=True))
    for line, index in enumerate(used):
        y = legend_top + line * 24
        parts.append(
            f'<rect x="{MARGIN_LEFT}" y="{_f(y)}" width="18" height="18" fill="{fill(index)}" '
            f'stroke="{GRID}" stroke-width="0.6"/>'
        )
        parts.append(_symbol(index, MARGIN_LEFT, y, 18, _ink(fill(index))))
        given = palette[index] if index < len(palette) else ""
        named = given if given and not given.startswith("#") else color_name(fill(index), lang)
        label = f"{color_letter(index)}: {named}"
        if index == chart.background:
            label += f" \u2013 {t('chart.colorwork_background', lang)}"
        parts.append(_text(MARGIN_LEFT + 26, y + 13, label, size=10.5))
    parts.append(_text(MARGIN_LEFT, height - 10, t("chart.colorwork_rows", lang), size=8.5))
    parts.append("</svg>")
    return "\n".join(parts)
