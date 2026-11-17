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
_CORNER_KINDS = {
    K.CORNER_SC, K.CORNER_DC, K.SQUARE_TURN, K.GRANNY_CORNER, K.GRANNY_START, K.HEX_CORNER, K.HEX_CORNER_SC,
}


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
    elif op.kind is K.MAGIC_RING:  # anillo magico con 6 pb
        one = [K.SC] * 6
    elif op.kind is K.CROCHET_INC:
        one = [base, base]
    elif op.kind is K.CORNER_SC:  # (1 pb, 2 cad, 1 pb)
        one = [K.SC, K.CH, K.CH, K.SC]
    elif op.kind is K.CORNER_DC:  # (2 pa, 2 cad, 2 pa)
        one = [K.DC, K.DC, K.CH, K.CH, K.DC, K.DC]
    elif op.kind is K.SQUARE_TURN:
        one = [K.TR, K.TR, K.CH, K.CH, K.TR, K.TR]
    elif op.kind is K.GRANNY_START:
        one = [K.DC] * 3 + [K.CH] * 2
    elif op.kind is K.GRANNY_CORNER:
        one = [K.DC] * 3 + [K.CH] * 2 + [K.DC] * 3 + [K.CH]
    elif op.kind is K.GRANNY_SIDE:
        one = [K.DC] * 3 + [K.CH]
    elif op.kind is K.HEX_CORNER:  # (1 pt, 1 cad, 1 pt)
        one = [base, K.CH, base]
    elif op.kind is K.HEX_CORNER_SC:
        one = [K.SC, K.SC]
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
        if op.kind in _CORNER_KINDS:
            if K.CH not in glyphs:  # esquina de pb: entre los 2 pb
                return position + len(glyphs) / 2
            first_ch = glyphs.index(K.CH)
            return position + first_ch + glyphs.count(K.CH) / 2
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


def _anchors(step: Step, base: StitchKind) -> list[float]:
    """Para cada simbolo de la vuelta, donde se teje: posicion (en puntos de
    la vuelta anterior, fraccionaria) dentro del tramo que consume su grupo.
    Las cadenas sueltas no consumen: quedan entre dos puntos."""
    out: list[float] = []
    position = 0.0

    def walk(items: Sequence[Item]) -> None:
        nonlocal position
        for item in items:
            if isinstance(item, Repeat):
                for _ in range(item.times):
                    walk(item.ops)
                continue
            consumed = item.consumes / item.times
            produced = len(expand(item, base)) // item.times
            for _ in range(item.times):
                out.extend(position + consumed * (j + 0.5) / produced for j in range(produced))
                position += consumed

    walk(step.items)
    return out


def corner_angle(sides: int) -> float:
    """Angulo (en pantalla) de la primera esquina: arriba a la derecha."""
    return -math.pi / 2 + math.pi / sides


def polygon_corners(half: float, sides: int = 4) -> list[tuple[float, float]]:
    """Esquinas de un poligono regular de apotema `half`, en sentido
    antihorario en pantalla desde arriba a la derecha (cuadrado o hexagono)."""
    radius = half / math.cos(math.pi / sides)
    first = corner_angle(sides)
    return [
        (radius * math.cos(first - 2 * math.pi * j / sides), radius * math.sin(first - 2 * math.pi * j / sides))
        for j in range(sides)
    ]


def _square_point(u: float, half: float, sides: int = 4) -> tuple[float, float]:
    """Punto del perimetro de un cuadrado (o hexagono); `u` en lados desde la
    esquina superior derecha, en sentido antihorario (en pantalla)."""
    corners = polygon_corners(half, sides)
    k = math.floor(u) % sides
    f = u - math.floor(u)
    (x0, y0), (x1, y1) = corners[k], corners[(k + 1) % sides]
    return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f


def _side_normal(u: float, sides: int) -> float:
    """Direccion hacia afuera del lado donde cae `u`."""
    return corner_angle(sides) - math.pi / sides - 2 * math.pi * (math.floor(u) % sides) / sides


def start_angle(
    steps: Sequence[Step],
    bases: Sequence[StitchKind],
    squares: Sequence[bool],
    spaced_ring: bool = False,
    sides: int = 4,
) -> float:
    """Angulo (en pantalla) donde empieza cada vuelta. Las vueltas redondas se
    giran para que la esquina de la vuelta que cuadra quede justo sobre el
    punto donde se teje (son simetricas: girarlas no cambia el tejido)."""
    for index in range(1, len(steps)):
        if squares[index] and not squares[index - 1]:
            anchors = _anchors(steps[index], bases[index])
            offset = corner_offset(steps[index], bases[index])
            worked = anchors[min(int(offset), len(anchors) - 1)]
            prev = len([k for item in steps[index - 1].items for k in expand(item, bases[index - 1], spaced_ring and index == 1)])
            return corner_angle(sides) + 2 * math.pi * worked / prev
    return -math.pi / 2


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
    sides: int = 4,
) -> tuple[list[str], set[StitchKind]]:
    """Dibuja las vueltas; devuelve (svg, simbolos usados).

    `span` < 2 pi dibuja solo esa porcion (desde arriba, en sentido
    antihorario): para motivos grandes alcanza con un sector de la simetria.
    """
    fraction = span / (2 * math.pi)
    start = start_angle(steps, bases, squares, spaced_ring, sides)
    perimeter = 2 * sides * math.tan(math.pi / sides)  # por unidad de apotema

    def turn(position: float, count: int) -> float:
        return start - 2 * math.pi * position / count

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
        if squares[index] and sides == 4:
            bands.append(
                f'<rect x="{_f(cx - r)}" y="{_f(cy - r)}" width="{_f(2 * r)}" height="{_f(2 * r)}" '
                f'fill="{fills[index]}" fill-opacity="0.38" stroke="{STROKE}" stroke-opacity="0.25" stroke-width="0.6"/>'
            )
        elif squares[index]:
            points =" ".join(f"{_f(cx + x)},{_f(cy + y)}" for x, y in polygon_corners(r, sides))
            bands.append(
                f'<polygon points="{points}" '
                f'fill="{fills[index]}" fill-opacity="0.38" stroke="{STROKE}" stroke-opacity="0.25" stroke-width="0.6"/>'
            )
        else:
            bands.append(
                f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="{fills[index]}" fill-opacity="0.38" '
                f'stroke="{STROKE}" stroke-opacity="0.25" stroke-width="0.6"/>'
            )
    if fraction < 1:
        reach = 1.5 * radius
        arc = [(start - span * k / 24) for k in range(25)]
        wedge = " ".join(f"{_f(cx + reach * math.cos(a))},{_f(cy + reach * math.sin(a))}" for a in arc)
        bands = clip_group("crochet-wedge", f'<polygon points="{_f(cx)},{_f(cy)} {wedge}"/>', bands)
    parts += bands
    parts.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(inner[0] * 0.8)}" fill="#ffffff" stroke="{STROKE}" stroke-width="1"/>')
    for index, row in enumerate(rows):
        if not row:
            continue
        base_r = inner[index] + 0.12 * unit
        count = len(row)
        offset = corner_offset(steps[index], bases[index]) if squares[index] else 0.0
        # Vuelta tejida sobre una redonda: cada simbolo nace del punto donde se
        # teje (su base) y llega a su lugar en el borde de la vuelta (su cabeza).
        linked = index > 0 and not squares[index - 1]
        anchors = _anchors(steps[index], bases[index]) if linked else []
        prev = len(rows[index - 1]) if linked else count
        if squares[index] and not linked:  # cuadrado sobre cuadrado (granny)
            slot = perimeter * base_r / count
            for i, kind in enumerate(row):
                u = (i + 0.5 - offset) / (count / sides)
                px, py = _square_point(u, base_r, sides)
                if (start - math.atan2(py, px)) % (2 * math.pi) > span:
                    continue
                # De pie sobre el lado (perpendicular al borde), no hacia el centro.
                angle = _side_normal(u, sides)
                parts.append(glyph(kind, cx + px, cy + py, angle, _HEIGHT.get(kind, 1.0) * unit, min(slot, 1.6 * unit)))
                used.add(kind)
        else:
            half = inner[index + 1] - 0.15 * unit
            slot = perimeter * half / count if squares[index] else 2 * math.pi * base_r / count
            for i, kind in enumerate(row):
                h = _HEIGHT.get(kind, 1.0) * unit
                if squares[index]:
                    tx, ty = _square_point((i + 0.5 - offset) / (count / sides), half, sides)
                else:
                    a = turn(i + 0.5, count)
                    tx, ty = (base_r + h) * math.cos(a), (base_r + h) * math.sin(a)
                if (start - math.atan2(ty, tx)) % (2 * math.pi) > span:
                    continue
                a0 = turn(anchors[i], prev) if linked else turn(i + 0.5, count)
                bx, by = base_r * math.cos(a0), base_r * math.sin(a0)
                direction = math.atan2(ty - by, tx - bx)
                reach = math.hypot(tx - bx, ty - by)
                if reach > 1.25 * h:  # simbolo de tamano normal en el borde y una guia fina hasta donde se teje
                    gx, gy = tx - h * math.cos(direction), ty - h * math.sin(direction)
                    parts.append(
                        f'<line x1="{_f(cx + bx)}" y1="{_f(cy + by)}" x2="{_f(cx + gx)}" y2="{_f(cy + gy)}" '
                        f'stroke="{STROKE}" stroke-width="0.6" stroke-opacity="0.55" stroke-dasharray="2 1.5"/>'
                    )
                    bx, by = gx, gy
                else:
                    h = max(h, reach)
                parts.append(glyph(kind, cx + bx, cy + by, direction, h, min(slot, 1.6 * unit)))
                used.add(kind)
        # Numero de vuelta, sobre el eje donde empieza la vuelta.
        if len(rows) <= 12 or (index + 1) % 5 == 0 or index == 0:
            mid = (inner[index] + inner[index + 1]) / 2
            nx = cx + mid * math.cos(start) - 0.9 * unit * math.sin(start)
            ny = cy + mid * math.sin(start) + 0.9 * unit * math.cos(start)
            parts.append(
                f'<text x="{_f(nx)}" y="{_f(ny + 3)}" font-size="{_f(min(11, max(7, 0.9 * unit)))}" '
                f'font-weight="700" fill="#b0452f" stroke="#ffffff" stroke-width="2.5" paint-order="stroke" '
                f'text-anchor="middle" font-family="Helvetica, Arial, sans-serif">{index + 1}</text>'
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
