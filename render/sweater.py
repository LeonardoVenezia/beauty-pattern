"""Esquema de pullover de frente con cotas por letra (A, B, C...).

Las letras son las mismas de la tabla de talles del documento: la letra de
cada medida es su posicion en `pattern.measurements`. Asi un solo dibujo sirve
para todos los talles, como en los patrones impresos. Con `values=True` (web,
un solo talle) cada letra lleva tambien su medida.

El dibujo es proporcional a las medidas del talle, pero no a escala exacta.
"""

from __future__ import annotations

import math

from engine.i18n import t
from engine.ir import Pattern
from render.draw import (
    FILL,
    STROKE,
    TEXT,
    TEXT_SOFT,
    _f,
    caption,
    clip_group,
    label,
    svg_document,
    title_block,
)

WIDTH, HEIGHT = 900.0, 720.0
_SLEEVE_ANGLE = math.radians(58)  # caida de la manga respecto de la horizontal


def letters_for(pattern: Pattern) -> dict[str, str]:
    return {m.key: chr(65 + i) for i, m in enumerate(pattern.measurements)}


def _value(pattern: Pattern, key: str) -> float | None:
    return next((m.value_cm for m in pattern.measurements if m.key == key), None)


def _dim(x1: float, y1: float, x2: float, y2: float, text: str, *, dx: float = 0, dy: float = -8) -> list[str]:
    """Linea de cota con topes perpendiculares y rotulo en el medio."""
    length = math.hypot(x2 - x1, y2 - y1) or 1.0
    nx, ny = -(y2 - y1) / length * 5, (x2 - x1) / length * 5
    parts = [
        f'<line x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}" stroke="{STROKE}" stroke-width="1"/>',
        f'<line x1="{_f(x1 - nx)}" y1="{_f(y1 - ny)}" x2="{_f(x1 + nx)}" y2="{_f(y1 + ny)}" stroke="{STROKE}" stroke-width="1"/>',
        f'<line x1="{_f(x2 - nx)}" y1="{_f(y2 - ny)}" x2="{_f(x2 + nx)}" y2="{_f(y2 + ny)}" stroke="{STROKE}" stroke-width="1"/>',
    ]
    mx, my = (x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy
    width = max(18.0, len(text) * 7.0)
    parts.append(
        f'<rect x="{_f(mx - width / 2)}" y="{_f(my - 11)}" width="{_f(width)}" height="15" fill="#ffffff" rx="3"/>'
    )
    parts.append(label(mx, my, text, size=12, weight="700", color=TEXT))
    return parts


def _yoke_band_stripes(pattern: Pattern, depth_cm: float) -> list[tuple[float, float, str]]:
    """(desde cm, hasta cm, color) de cada guarda de jacquard del canesu."""
    yoke = next((s for s in pattern.sections if s.id == "yoke"), None)
    if yoke is None or not yoke.steps:
        return []
    colors = pattern.materials.colors
    rows = len(yoke.steps)
    stripes: list[tuple[float, float, str]] = []
    for index, step in enumerate(yoke.steps):
        if step.note_key != "pattern.note.yoke_chart":
            continue
        contrast = ord(dict(step.note_params).get("fg", "B")) - 65
        color = colors[contrast] if 0 <= contrast < len(colors) else STROKE
        y0, y1 = depth_cm * index / rows, depth_cm * (index + 1) / rows
        if stripes and stripes[-1][2] == color and abs(stripes[-1][1] - y0) < 1e-9:
            stripes[-1] = (stripes[-1][0], y1, color)
        else:
            stripes.append((y0, y1, color))
    return stripes


def render_sweater_svg(pattern: Pattern, lang: str, *, values: bool) -> str:
    letters = letters_for(pattern)
    unit = t(f"unit.{pattern.params.unidades}", lang)

    def tag(key: str) -> str:
        letter = letters[key]
        if not values:
            return letter
        cm = _value(pattern, key) or 0.0
        shown = cm / 2.54 if pattern.params.unidades == "in" else cm
        return f"{letter} {round(shown * 2) / 2:g} {unit}"

    bust = _value(pattern, "bust") or 100.0
    body_len = _value(pattern, "body_length") or 60.0
    yoke = _value(pattern, "yoke_depth") or _value(pattern, "armhole") or 22.0
    sleeve_len = _value(pattern, "sleeve_length")
    upper_arm = _value(pattern, "upper_arm") or bust * 0.33
    wrist = _value(pattern, "wrist") or upper_arm * 0.55
    neck = _value(pattern, "neck") or bust * 0.38

    half = bust / 4  # medio frente
    neck_w = neck / 3.0
    shoulder_drop = 3.0
    sleeve = sleeve_len - yoke if sleeve_len else 0.0  # largo desde la axila
    reach = math.cos(_SLEEVE_ANGLE) * sleeve + upper_arm / 2
    total_w = 2 * (half + reach)
    total_h = body_len + 6
    scale = min((WIDTH - 160) / total_w, (HEIGHT - 190) / total_h)
    cx, top = WIDTH / 2, 120.0

    def p(x: float, y: float) -> tuple[float, float]:
        return cx + x * scale, top + y * scale

    family = pattern.meta.family
    cardigan = family in {"cardigan", "crochet_cardigan"}
    escote = pattern.spec.escote.value if pattern.spec.escote else None
    # Mismo criterio que el motor (flat._plan_front_neck): el cardigan de dos
    # agujas lleva escote en V salvo que la foto muestre uno redondo/alto.
    v_neck = family == "cardigan" and escote not in {"crew", "turtleneck", "funnel"}
    neck_depth = 6.0
    shoulder = (half, shoulder_drop) if sleeve > 0 or not family.endswith("vest") else (half * 0.8, shoulder_drop)
    underarm = (half, yoke)
    ux, uy = math.cos(_SLEEVE_ANGLE), math.sin(_SLEEVE_ANGLE)
    sleeve_pts: list[tuple[float, float]] = []
    if sleeve > 0:
        mid = ((shoulder[0] + underarm[0]) / 2, (shoulder[1] + underarm[1]) / 2)
        cuff = (mid[0] + ux * sleeve, mid[1] + uy * sleeve)
        px, py = -uy, ux  # perpendicular
        half_cuff = wrist / 4
        sleeve_pts = [
            (cuff[0] - px * half_cuff, cuff[1] - py * half_cuff),
            (cuff[0] + px * half_cuff, cuff[1] + py * half_cuff),
        ]

    # Sin manga, la sisa entra hacia el cuerpo y sale abajo hasta la axila.
    armhole = [] if sleeve_pts or shoulder[0] == half else [(shoulder[0], yoke * 0.7)]
    right = [(neck_w / 2, 0.0), shoulder, *sleeve_pts, *armhole, underarm, (half, body_len)]
    left = [(-x, y) for x, y in reversed(right)]
    outline = [*right, *left]
    d = "M " + " L ".join(f"{_f(p(x, y)[0])} {_f(p(x, y)[1])}" for x, y in outline)
    nl, nr = p(-neck_w / 2, 0), p(neck_w / 2, 0)
    if v_neck:
        nb = p(0, yoke)
        d += f" L {_f(nb[0])} {_f(nb[1])} L {_f(nr[0])} {_f(nr[1])} Z"
        neck_bottom = yoke
    else:
        nb = p(0, neck_depth * 2)
        d += f" Q {_f(nb[0])} {_f(nb[1])} {_f(nr[0])} {_f(nr[1])} Z"
        neck_bottom = neck_depth
    parts = [f'<path d="{d}" fill="{FILL}" stroke="{STROKE}" stroke-width="1.8" stroke-linejoin="round"/>']
    stripes = _yoke_band_stripes(pattern, yoke)
    if stripes:  # guardas de jacquard del canesu, a su altura y en su color
        x0, x1 = p(-total_w / 2, 0)[0], p(total_w / 2, 0)[0]
        rects = [
            f'<rect x="{_f(x0)}" y="{_f(p(0, y0)[1])}" width="{_f(x1 - x0)}" '
            f'height="{_f(max(1.0, (y1 - y0) * scale))}" fill="{color}" fill-opacity="0.75"/>'
            for y0, y1, color in stripes
        ]
        parts += clip_group("yoke-bands", f'<path d="{d}"/>', rects)
        parts.append(f'<path d="{d}" fill="none" stroke="{STROKE}" stroke-width="1.8" stroke-linejoin="round"/>')
    if cardigan:  # abertura del frente con su tapa de botones
        top_y, hem_y = p(0, neck_bottom)[1], p(0, body_len)[1]
        band = 1.5 * scale
        parts.append(
            f'<rect x="{_f(cx - band)}" y="{_f(top_y)}" width="{_f(2 * band)}" height="{_f(hem_y - top_y)}" '
            f'fill="none" stroke="{STROKE}" stroke-width="1" stroke-dasharray="4 3"/>'
        )
        parts.append(f'<line x1="{_f(cx)}" y1="{_f(top_y)}" x2="{_f(cx)}" y2="{_f(hem_y)}" stroke="{STROKE}" stroke-width="1.4"/>')

    # Cotas.
    if "neck" in letters:
        y = p(0, -2.5)[1]
        parts += _dim(nl[0], y, nr[0], y, tag("neck"))
    if "bust" in letters:
        y = p(0, yoke + 3)[1]
        parts += _dim(p(-half, 0)[0] + 4, y, p(half, 0)[0] - 4, y, tag("bust"), dx=half * scale / 2 if cardigan else 0, dy=-6)
    if "body_length" in letters:
        x = p(-half * 0.45, 0)[0]
        parts += _dim(x, p(0, shoulder_drop)[1], x, p(0, body_len)[1], tag("body_length"), dy=0)
    depth_key = "yoke_depth" if "yoke_depth" in letters else ("armhole" if "armhole" in letters else None)
    if depth_key:
        x = p(half * 0.45, 0)[0]
        parts += _dim(x, p(0, 0)[1], x, p(0, yoke)[1], tag(depth_key), dy=0)
    if sleeve_pts:
        s0, u0 = p(*shoulder), p(*underarm)
        if "upper_arm" in letters:
            parts += _dim(s0[0] + 6, s0[1], u0[0] + 6, u0[1], tag("upper_arm"), dx=26, dy=4)
        c0, c1 = p(*sleeve_pts[0]), p(*sleeve_pts[1])
        if "wrist" in letters:
            parts += _dim(c0[0], c0[1], c1[0], c1[1], tag("wrist"), dx=18, dy=16)
        if "sleeve_length" in letters:
            ox, oy = -uy * 14, ux * 14
            a, b = p(*shoulder), p(*sleeve_pts[0])
            parts += _dim(a[0] - ox, a[1] - oy, b[0] - ox, b[1] - oy, tag("sleeve_length"), dx=18, dy=-6)

    title = t(pattern.meta.title_key, lang)
    subtitle = t("schematic.letters_note", lang) if not values else t(
        "schematic.size_measures_in", lang, size=pattern.meta.size, unit=unit
    )
    head = title_block(WIDTH, 42, title, subtitle)
    entries = [f"{letters[k]}: {t(f'measure.{k}', lang)}" for k in letters]
    legend = [
        label(WIDTH / 2, HEIGHT - 62 + row * 15, "   ".join(entries[row * 4 : row * 4 + 4]), size=10, color=TEXT_SOFT)
        for row in range((len(entries) + 3) // 4)
    ]
    tail = [caption(WIDTH, HEIGHT - 20, t("schematic.caption", lang))]
    return svg_document(WIDTH, HEIGHT, title, t("pattern.schematic", lang), head + parts + legend + tail)
