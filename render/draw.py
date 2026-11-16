"""Kit de dibujo tecnico para esquemas SVG de patrones.

Una sola fuente de verdad: el SVG que ve la web es el mismo que se incrusta
en el PDF (convertido con svglib). Por eso el kit se restringe a primitivas
que svglib soporta bien: path, rect, circle, line, polygon, text, clipPath y
stroke-dasharray; sin <marker>, sin <use> y con la familia Helvetica/Arial.
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

STROKE = "#6b4f3a"
STROKE_SOFT = "#b08b6e"
STROKE_FAINT = "#d8c3ac"
FILL = "#f2e8dc"
FILL_ALT = "#e6d6c4"
TEXT = "#3a2a1e"
TEXT_SOFT = "#8a6a50"
FONT = "Helvetica, Arial, sans-serif"

ARROW = 7.0
TICK = 4.0


def _f(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def svg_document(
    width: float,
    height: float,
    title: str,
    desc: str,
    parts: list[str],
    title_id: str = "schematic-title",
    desc_id: str = "schematic-desc",
) -> str:
    return "".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{_f(width)}" height="{_f(height)}" '
            f'viewBox="0 0 {_f(width)} {_f(height)}" role="img" '
            f'aria-labelledby="{title_id} {desc_id}">',
            f'<title id="{title_id}">{escape(title)}</title>',
            f'<desc id="{desc_id}">{escape(desc)}</desc>',
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            *parts,
            "</svg>",
        ]
    )


def label(
    x: float,
    y: float,
    text: str,
    *,
    size: float = 11,
    anchor: str = "middle",
    color: str = TEXT,
    weight: str | None = None,
) -> str:
    weight_attr = f' font-weight="{weight}"' if weight else ""
    return (
        f'<text x="{_f(x)}" y="{_f(y)}" text-anchor="{anchor}" '
        f'font-family="{FONT}" font-size="{_f(size)}" fill="{color}"'
        f"{weight_attr}>{escape(text)}</text>"
    )


def _arrow_h(x: float, y: float, direction: int) -> str:
    """Punta de flecha horizontal en (x, y); direction -1 apunta a la izquierda."""
    tip = x + direction * ARROW
    base = x
    return (
        f'<polygon points="{_f(tip)},{_f(y)} {_f(base)},{_f(y - 3.2)} '
        f'{_f(base)},{_f(y + 3.2)}" fill="{STROKE}"/>'
    )


def _arrow_v(x: float, y: float, direction: int) -> str:
    """Punta de flecha vertical en (x, y); direction -1 apunta hacia arriba."""
    tip = y + direction * ARROW
    base = y
    return (
        f'<polygon points="{_f(x)},{_f(tip)} {_f(x - 3.2)},{_f(base)} '
        f'{_f(x + 3.2)},{_f(base)}" fill="{STROKE}"/>'
    )


def dim_h(
    x1: float,
    x2: float,
    y: float,
    lines: tuple[str, ...],
    *,
    extension: float = 0.0,
    size: float = 11,
) -> list[str]:
    """Cota horizontal con flechas en ambos extremos y rotulo centrado.

    `extension` dibuja lineas de extension hacia abajo (o arriba si es
    negativo) en cada extremo, para conectar la cota con la pieza.
    """
    parts = [
        f'<line x1="{_f(x1)}" y1="{_f(y)}" x2="{_f(x2)}" y2="{_f(y)}" '
        f'stroke="{STROKE}" stroke-width="1"/>',
        _arrow_h(x1, y, -1),
        _arrow_h(x2, y, 1),
    ]
    for x in (x1, x2):
        if extension:
            parts.append(
                f'<line x1="{_f(x)}" y1="{_f(y)}" x2="{_f(x)}" '
                f'y2="{_f(y + extension)}" stroke="{STROKE}" stroke-width="0.7"/>'
            )
    text_block = max(size * 1.35, 14.0) * len(lines)
    rect_w = max(len(max(lines, key=len)) * size * 0.58, 30.0)
    parts.append(
        f'<rect x="{_f((x1 + x2) / 2 - rect_w / 2)}" '
        f'y="{_f(y - text_block - 4)}" width="{_f(rect_w)}" '
        f'height="{_f(text_block + 2)}" fill="#ffffff"/>'
    )
    for index, line in enumerate(lines):
        parts.append(
            label(
                (x1 + x2) / 2,
                y - text_block + index * (text_block / len(lines)) + size * 0.2,
                line,
                size=size,
            )
        )
    return parts


def dim_v(
    y1: float,
    y2: float,
    x: float,
    lines: tuple[str, ...],
    *,
    side: str = "right",
    extension: float = 0.0,
    size: float = 11,
) -> list[str]:
    """Cota vertical con flechas y rotulo horizontal al costado.

    `side` decide si el rotulo va a la derecha o a la izquierda de la linea;
    `extension` dibuja lineas de extension hacia la pieza (positivo: derecha).
    """
    parts = [
        f'<line x1="{_f(x)}" y1="{_f(y1)}" x2="{_f(x)}" y2="{_f(y2)}" '
        f'stroke="{STROKE}" stroke-width="1"/>',
        _arrow_v(x, y1, -1),
        _arrow_v(x, y2, 1),
    ]
    for yy in (y1, y2):
        if extension:
            parts.append(
                f'<line x1="{_f(x)}" y1="{_f(yy)}" x2="{_f(x + extension)}" '
                f'y2="{_f(yy)}" stroke="{STROKE}" stroke-width="0.7"/>'
            )
    anchor_x = x + 10 if side == "right" else x - 10
    anchor = "start" if side == "right" else "end"
    step = size * 1.35
    top = (y1 + y2) / 2 - (len(lines) - 1) * step / 2 + size * 0.35
    for index, line in enumerate(lines):
        parts.append(label(anchor_x, top + index * step, line, size=size, anchor=anchor))
    return parts


def callout(
    x: float,
    y: float,
    lines: tuple[str, ...],
    *,
    dx: float,
    dy: float,
    size: float = 11,
    anchor: str | None = None,
) -> list[str]:
    """Flecha diagonal con rotulo: para contornos dentro de la prenda."""
    end_x, end_y = x + dx, y + dy
    parts = [
        f'<circle cx="{_f(x)}" cy="{_f(y)}" r="2.4" fill="{STROKE}"/>',
        f'<line x1="{_f(x)}" y1="{_f(y)}" x2="{_f(end_x)}" y2="{_f(end_y)}" '
        f'stroke="{STROKE}" stroke-width="0.9"/>',
    ]
    if anchor is None:
        anchor = "start" if dx >= 0 else "end"
    step = size * 1.35
    text_x = end_x + (6 if anchor == "start" else -6)
    for index, line in enumerate(lines):
        parts.append(
            label(
                text_x,
                end_y + index * step - (len(lines) - 1) * step / 2,
                line,
                size=size,
                anchor=anchor,
            )
        )
    return parts


def knit_texture(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 12.0,
    color: str = "#c9ad91",
) -> list[str]:
    """Textura de punto jersey: filas de V intercaladas, ajustada al rect."""
    cols = max(1, int(w / size))
    rows = max(1, int(h / size))
    cell_w = w / cols
    cell_h = h / rows
    half_w = cell_w * 0.32
    half_h = cell_h * 0.38
    parts = [f'<g stroke="{color}" stroke-width="1" fill="none" stroke-linecap="round">']
    for row in range(rows):
        cy = y + (row + 0.5) * cell_h
        offset = half_w if row % 2 else 0.0
        for col in range(cols + 1):
            cx = x + col * cell_w + offset - (cell_w / 2 if row % 2 else 0)
            if x - 1 <= cx - half_w and cx + half_w <= x + w + 1:
                parts.append(
                    f'<path d="M {_f(cx - half_w)} {_f(cy - half_h)} '
                    f'L {_f(cx)} {_f(cy + half_h)} L {_f(cx + half_w)} {_f(cy - half_h)}"/>'
                )
    parts.append("</g>")
    return parts


def crochet_texture(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 12.0,
    color: str = "#c9ad91",
) -> list[str]:
    """Textura de tejido en crochet: cruces alternadas, ajustada al rect."""
    cols = max(1, int(w / size))
    rows = max(1, int(h / size))
    cell_w = w / cols
    cell_h = h / rows
    arm = min(cell_w, cell_h) * 0.28
    parts = [f'<g stroke="{color}" stroke-width="1" fill="none" stroke-linecap="round">']
    for row in range(rows):
        cy = y + (row + 0.5) * cell_h
        offset = cell_w / 2 if row % 2 else 0.0
        for col in range(cols):
            cx = x + col * cell_w + offset + cell_w * 0.25
            if cx + arm <= x + w + 1:
                parts.append(
                    f'<path d="M {_f(cx - arm)} {_f(cy - arm)} '
                    f"L {_f(cx + arm)} {_f(cy + arm)} "
                    f"M {_f(cx + arm)} {_f(cy - arm)} "
                    f'L {_f(cx - arm)} {_f(cy + arm)}"/>'
                )
    parts.append("</g>")
    return parts


def clip_group(clip_id: str, clip_path: str, parts: list[str]) -> list[str]:
    """Envuelve `parts` en un clipPath (svglib lo soporta)."""
    return [
        f'<defs><clipPath id="{escape(clip_id)}">',
        clip_path,
        "</clipPath></defs>",
        f'<g clip-path="url(#{escape(clip_id)})">',
        *parts,
        "</g>",
    ]


def title_block(width: float, y: float, title: str, subtitle: str | None) -> list[str]:
    """Encabezado del esquema: titulo centrado, subtitulo y filete fino."""
    parts = [label(width / 2, y, title, size=17, weight="700", color=TEXT)]
    next_y = y + 22
    if subtitle:
        parts.append(label(width / 2, next_y, subtitle, size=12, color=TEXT_SOFT))
        next_y += 17
    parts.append(
        f'<line x1="50" y1="{_f(next_y)}" x2="{_f(width - 50)}" y2="{_f(next_y)}" '
        f'stroke="{STROKE_FAINT}" stroke-width="1"/>'
    )
    return parts


def caption(width: float, y: float, text: str) -> str:
    return label(width / 2, y, text, size=10, color=TEXT_SOFT)


def dashed_line(x1: float, y1: float, x2: float, y2: float, *, color: str = STROKE_SOFT) -> str:
    return (
        f'<line x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}" '
        f'stroke="{color}" stroke-width="1" stroke-dasharray="5 4"/>'
    )


def shape_path(d: str, *, fill: str = FILL, stroke: str = STROKE, width: float = 2) -> str:
    return (
        f'<path d="{d}" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{_f(width)}" stroke-linejoin="round"/>'
    )


def shape_rect(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    rx: float = 0,
    fill: str = FILL,
    stroke: str = STROKE,
    width: float = 2,
) -> str:
    return (
        f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" '
        f'rx="{_f(rx)}" fill="{fill}" stroke="{stroke}" stroke-width="{_f(width)}"/>'
    )


# Nombres de color frecuentes (es/en) -> tono de muestra. Lo desconocido usa
# una escala neutra; el texto siempre nombra el color.
_NAMED = {
    "crema": "#efe6d2",
    "cream": "#efe6d2",
    "blanco": "#f7f5f0",
    "white": "#f7f5f0",
    "beige": "#d9c7a7",
    "verde": "#6fbf9f",
    "green": "#6fbf9f",
    "rosa": "#cf9182",
    "pink": "#cf9182",
    "gris": "#a9adb0",
    "grey": "#a9adb0",
    "gray": "#a9adb0",
    "azul": "#6f8fbf",
    "blue": "#6f8fbf",
    "rojo": "#c0504d",
    "red": "#c0504d",
    "amarillo": "#e8c95a",
    "yellow": "#e8c95a",
    "naranja": "#e39252",
    "orange": "#e39252",
    "violeta": "#9a7cc0",
    "lila": "#b9a2d6",
    "purple": "#9a7cc0",
    "negro": "#3b3b3b",
    "black": "#3b3b3b",
    "marron": "#8a6247",
    "marrón": "#8a6247",
    "brown": "#8a6247",
    "celeste": "#9cc9e3",
    "mostaza": "#c9a13b",
    "terracota": "#b8653f",
}
_NEUTRAL = ["#efe6d2", "#d9c7a7", "#c4ad8a", "#a88f6d"]


def swatch(name: str, index: int = 0) -> str:
    """Tono del color nombrado; tambien "verde salvia" o "sage_green" (por
    la palabra conocida que aparezca)."""
    key = name.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", key):
        return key
    if key in _NAMED:
        return _NAMED[key]
    for word in key.replace("_", " ").replace("-", " ").split():
        if word in _NAMED:
            return _NAMED[word]
    return _NEUTRAL[index % len(_NEUTRAL)]
