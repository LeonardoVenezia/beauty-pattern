"""Grafico de simbolos de crochet en redondo (motivos, granny square).

Cada punto producido por una vuelta verificada de la IR es un simbolo
(convencion Craft Yarn Council: cadena = ovalo, pb = +, mpa = T, pa = T con
una barra, pad = T con dos). Las vueltas van del centro hacia afuera; las que
cuadran el motivo se reparten sobre el perimetro de un cuadrado con las
esquinas donde caen las cadenas de esquina. Siempre lleva su leyenda.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from html import escape

from engine.i18n import t
from engine.ir import Item, Op, Repeat, Step
from engine.stitches.kinds import StitchKind
from render.draw import STROKE, TEXT, _f, clip_group, label

K = StitchKind
# Altura del simbolo en "alturas de pb" (ASUNCION de proporciones del dibujo).
_HEIGHT = {
    K.SC: 1.0, K.HDC: 1.4, K.DC: 1.9, K.TR: 2.5, K.CLUSTER: 1.9, K.POPCORN: 1.9,
    K.PUFF: 1.9, K.CH: 0.8, K.SLST: 0.6,
}
_CORNER_CH = 2  # las esquinas llevan 2 cad


def expand(item: Item, base: StitchKind, spaced: bool = False) -> list[StitchKind]:
    """Simbolos (en orden) de un item; `base` es el punto de la vuelta y
    `spaced` si es calada (en el anillo alterna grupo y cadena)."""
    if isinstance(item, Repeat):
        return [kind for op in item.ops for kind in expand(op, base, spaced)] * item.times
    op: Op = item
    one: list[StitchKind]
    if op.kind is K.RING:
        width = op.width or 0
        one = [base, K.CH] * (width // 2) if spaced else [base] * width
    elif op.kind is K.SKIP:
        one = []
    elif op.kind is K.CROCHET_INC:
        one = [base, base]
    elif op.kind is K.CORNER_SC:
        one = [base, K.CH, K.CH, base]
    elif op.kind is K.CORNER_DC:
        one = [base, base, K.CH, K.CH, base, base]
    elif op.kind is K.SQUARE_TURN:
        one = [K.TR, K.TR, K.CH, K.CH, K.TR, K.TR]
    elif op.kind is K.GRANNY_START:
        one = [K.DC] * 3 + [K.CH] * 2
    elif op.kind is K.GRANNY_CORNER:
        one = [K.DC] * 3 + [K.CH] * 2 + [K.DC] * 3 + [K.CH]
    elif op.kind is K.GRANNY_SIDE:
        one = [K.DC] * 3 + [K.CH]
    else:
        one = [op.kind]
    return one * op.times


def corner_offset(step: Step, base: StitchKind) -> float:
    """Posicion (en simbolos) del centro de la primera esquina de la vuelta."""
    sector = step.items[0]
    ops = sector.ops if isinstance(sector, Repeat) else (sector,)
    position = 0.0
    for op in ops:
        glyphs = expand(op, base)
        if op.kind in {K.CORNER_SC, K.CORNER_DC, K.SQUARE_TURN, K.GRANNY_CORNER, K.GRANNY_START}:
            first_ch = glyphs.index(K.CH)
            return position + first_ch + _CORNER_CH / 2
        position += len(glyphs)
    return 0.0


def glyph(kind: StitchKind, x: float, y: float, angle: float, h: float, w: float) -> str:
    """Simbolo con la base en (x, y) apuntando hacia afuera (`angle`, rad)."""
    deg = math.degrees(angle) + 90
    s = f'stroke="{STROKE}" stroke-width="{_f(max(0.6, min(1.3, w / 7)))}" fill="none" stroke-linecap="round"'
    body: list[str] = []
    stem = f'<line x1="0" y1="0" x2="0" y2="{_f(-h)}" {s}/>'
    bar = f'<line x1="{_f(-0.38 * w)}" y1="{_f(-h)}" x2="{_f(0.38 * w)}" y2="{_f(-h)}" {s}/>'

    def slash(at: float) -> str:
        return f'<line x1="{_f(-0.28 * w)}" y1="{_f(-at * h + 0.08 * h)}" x2="{_f(0.28 * w)}" y2="{_f(-at * h - 0.08 * h)}" {s}/>'

    if kind is K.CH:
        body.append(f'<ellipse cx="0" cy="{_f(-h / 2)}" rx="{_f(0.42 * w)}" ry="{_f(min(0.22 * w, h / 2))}" {s}/>')
    elif kind is K.SLST:
        body.append(f'<circle cx="0" cy="{_f(-h / 2)}" r="{_f(max(1.0, 0.18 * w))}" fill="{STROKE}"/>')
    elif kind is K.SC:
        body.append(f'<line x1="0" y1="{_f(-0.1 * h)}" x2="0" y2="{_f(-0.9 * h)}" {s}/>')
        body.append(f'<line x1="{_f(-0.32 * w)}" y1="{_f(-h / 2)}" x2="{_f(0.32 * w)}" y2="{_f(-h / 2)}" {s}/>')
    elif kind in {K.HDC, K.DC, K.TR}:
        body += [stem, bar]
        if kind is K.DC:
            body.append(slash(0.55))
        if kind is K.TR:
            body += [slash(0.45), slash(0.65)]
    elif kind is K.CLUSTER:
        for dx in (-0.4 * w, 0.0, 0.4 * w):
            body.append(f'<path d="M 0 0 Q {_f(dx * 1.6)} {_f(-h / 2)} 0 {_f(-h)}" {s}/>')
        body.append(bar)
    elif kind is K.PUFF:
        body.append(f'<ellipse cx="0" cy="{_f(-h / 2)}" rx="{_f(0.3 * w)}" ry="{_f(h / 2)}" {s}/>')
    elif kind is K.POPCORN:
        for dx in (-0.36 * w, 0.0, 0.36 * w):
            body.append(f'<line x1="0" y1="0" x2="{_f(dx)}" y2="{_f(-0.8 * h)}" {s}/>')
        body.append(f'<ellipse cx="0" cy="{_f(-0.85 * h)}" rx="{_f(0.4 * w)}" ry="{_f(0.14 * h)}" {s}/>')
    else:  # simbolo generico: un punto
        body.append(f'<circle cx="0" cy="{_f(-h / 2)}" r="{_f(0.2 * w)}" {s}/>')
    return f'<g transform="translate({_f(x)} {_f(y)}) rotate({_f(deg)})">{"".join(body)}</g>'


def _square_point(u: float, half: float) -> tuple[float, float]:
    """Punto del perimetro de un cuadrado; `u` en lados desde la esquina
    superior derecha, en sentido antihorario (en pantalla)."""
    corners = [(half, -half), (-half, -half), (-half, half), (half, half)]
    k = math.floor(u) % 4
    f = u - math.floor(u)
    (x0, y0), (x1, y1) = corners[k], corners[(k + 1) % 4]
    return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f


def draw_rounds(
    steps: Sequence[Step],
    bases: Sequence[StitchKind],
    squares: Sequence[bool],
    fills: Sequence[str],
    cx: float,
    cy: float,
    radius: float,
    *,
    ring_center: bool = True,
    spaced_ring: bool = False,
    span: float = 2 * math.pi,
) -> tuple[list[str], set[StitchKind]]:
    """Dibuja las vueltas; devuelve (svg, simbolos usados).

    `span` < 2 pi dibuja solo esa porcion (desde arriba, en sentido
    antihorario): para motivos grandes alcanza con un sector de la simetria.
    """
    fraction = span / (2 * math.pi)
    rows = [
        [k for item in step.items for k in expand(item, base, spaced_ring and index == 0)]
        for index, (step, base) in enumerate(zip(steps, bases, strict=True))
    ]
    heights = [max((_HEIGHT.get(k, 1.0) for k in row), default=1.0) + 0.35 for row in rows]
    centre_r = 1.2 if ring_center else 0.6
    unit = radius / (centre_r + sum(heights))
    parts: list[str] = []
    used: set[StitchKind] = set()
    inner = [centre_r * unit]
    for h in heights:
        inner.append(inner[-1] + h * unit)
    # Franjas de color por vuelta (de afuera hacia adentro).
    bands: list[str] = []
    for index in range(len(rows) - 1, -1, -1):
        r = inner[index + 1]
        if squares[index]:
            bands.append(
                f'<rect x="{_f(cx - r)}" y="{_f(cy - r)}" width="{_f(2 * r)}" height="{_f(2 * r)}" '
                f'fill="{fills[index]}" fill-opacity="0.38" stroke="{STROKE}" stroke-opacity="0.25" stroke-width="0.6"/>'
            )
        else:
            bands.append(
                f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="{fills[index]}" fill-opacity="0.38" '
                f'stroke="{STROKE}" stroke-opacity="0.25" stroke-width="0.6"/>'
            )
    if fraction < 1:
        reach = 1.5 * radius
        arc = [(-math.pi / 2 - span * k / 24) for k in range(25)]
        wedge = " ".join(f"{_f(cx + reach * math.cos(a))},{_f(cy + reach * math.sin(a))}" for a in arc)
        bands = clip_group("crochet-wedge", f'<polygon points="{_f(cx)},{_f(cy)} {wedge}"/>', bands)
    parts += bands
    parts.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(inner[0] * 0.8)}" fill="#ffffff" stroke="{STROKE}" stroke-width="1"/>')
    for index, row in enumerate(rows):
        if not row:
            continue
        base_r = inner[index] + 0.12 * unit
        count = len(row)
        if squares[index]:
            offset = corner_offset(steps[index], bases[index])
            slot = 8 * base_r / count
            for i, kind in enumerate(row):
                px, py = _square_point((i + 0.5 - offset) / (count / 4), base_r)
                angle = math.atan2(py, px)
                if (-math.pi / 2 - angle) % (2 * math.pi) > span:
                    continue
                parts.append(glyph(kind, cx + px, cy + py, angle, _HEIGHT.get(kind, 1.0) * unit, min(slot, 1.6 * unit)))
                used.add(kind)
        else:
            slot = 2 * math.pi * base_r / count
            for i, kind in enumerate(row):
                if (i + 0.5) / count > fraction:
                    continue
                angle = -math.pi / 2 - 2 * math.pi * (i + 0.5) / count
                x, y = cx + base_r * math.cos(angle), cy + base_r * math.sin(angle)
                parts.append(glyph(kind, x, y, angle, _HEIGHT.get(kind, 1.0) * unit, min(slot, 1.6 * unit)))
                used.add(kind)
        # Numero de vuelta, sobre el eje vertical (donde empieza la vuelta).
        if len(rows) <= 12 or (index + 1) % 5 == 0 or index == 0:
            mid = (inner[index] + inner[index + 1]) / 2
            parts.append(
                f'<text x="{_f(cx + 0.9 * unit)}" y="{_f(cy - mid + 3)}" font-size="{_f(min(11, max(7, 0.9 * unit)))}" '
                f'font-weight="700" fill="#b0452f" stroke="#ffffff" stroke-width="2.5" paint-order="stroke" '
                f'font-family="Helvetica, Arial, sans-serif">{index + 1}</text>'
            )
    return parts, used


_ORDER = [K.CH, K.SLST, K.SC, K.HDC, K.DC, K.TR, K.CLUSTER, K.PUFF, K.POPCORN]


def legend(used: set[StitchKind], lang: str, x: float, y: float, width: float) -> list[str]:
    """Leyenda: simbolo = abreviatura (nombre), en filas."""
    kinds = [k for k in _ORDER if k in used]
    if not kinds:
        return []
    per_row = 4
    col = width / per_row
    parts = [label(x + width / 2, y - 14, t("chart.legend", lang), size=12, weight="700", color=TEXT)]
    for index, kind in enumerate(kinds):
        gx = x + (index % per_row) * col + 14
        gy = y + (index // per_row) * 30 + 14
        parts.append(glyph(kind, gx, gy, -math.pi / 2, 22 * _HEIGHT.get(kind, 1.0) / 2.5, 14))
        abbr, meaning = t(f"glossary.{kind.value}", lang).split("::", 1)
        short = meaning.split(":")[0].split("(")[0].strip()
        parts.append(
            f'<text x="{_f(gx + 14)}" y="{_f(gy - 3)}" font-size="11" fill="{TEXT}" '
            f'font-family="Helvetica, Arial, sans-serif"><tspan font-weight="700">{escape(abbr)}</tspan> {escape(short)}</text>'
        )
    return parts
