"""Esquema de un juguete (amigurumi): el muneco armado, de frente.

Cada pieza es una forma simple (circulo, pera, capsula, triangulo) con el
tamano que sale de la IR verificada: contorno maximo y vueltas de cada
seccion. Los rotulos van en una columna a la derecha, con lineas guia, para
que ningun texto quede encima del dibujo.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import pi

from engine.i18n import t
from engine.ir import Pattern, Section
from engine.rounding import round_half_up
from engine.spec import resolve_gauge
from render.draw import (
    FILL,
    FILL_ALT,
    STROKE,
    TEXT,
    TEXT_SOFT,
    _f,
    caption,
    dim_v,
    label,
    shape_path,
    svg_document,
    title_block,
)

WIDTH, HEIGHT = 900.0, 720.0
TOP, BOTTOM = 120.0, 640.0
FIG_CX = 330.0  # centro del muneco
FIG_W = 400.0  # ancho disponible para el muneco
LABEL_X = 610.0
K = 0.5523  # cubicas que aproximan un cuarto de elipse


def _ellipse(cx: float, cy: float, rx: float, ry: float) -> str:
    """Elipse como path (svglib no maneja bien <ellipse> con estilos)."""
    kx, ky = rx * K, ry * K
    return (
        f"M {_f(cx - rx)} {_f(cy)} "
        f"C {_f(cx - rx)} {_f(cy - ky)} {_f(cx - kx)} {_f(cy - ry)} {_f(cx)} {_f(cy - ry)} "
        f"C {_f(cx + kx)} {_f(cy - ry)} {_f(cx + rx)} {_f(cy - ky)} {_f(cx + rx)} {_f(cy)} "
        f"C {_f(cx + rx)} {_f(cy + ky)} {_f(cx + kx)} {_f(cy + ry)} {_f(cx)} {_f(cy + ry)} "
        f"C {_f(cx - kx)} {_f(cy + ry)} {_f(cx - rx)} {_f(cy + ky)} {_f(cx - rx)} {_f(cy)} Z"
    )


def _capsule(cx: float, top: float, w: float, h: float) -> str:
    """Capsula vertical (brazo): semicirculos arriba y abajo, en px."""
    r = w / 2
    k = r * K
    y1, y2 = top + r, top + max(h, w) - r
    return (
        f"M {_f(cx - r)} {_f(y1)} "
        f"C {_f(cx - r)} {_f(y1 - k)} {_f(cx - k)} {_f(top)} {_f(cx)} {_f(top)} "
        f"C {_f(cx + k)} {_f(top)} {_f(cx + r)} {_f(y1 - k)} {_f(cx + r)} {_f(y1)} "
        f"L {_f(cx + r)} {_f(y2)} "
        f"C {_f(cx + r)} {_f(y2 + k)} {_f(cx + k)} {_f(y2 + r)} {_f(cx)} {_f(y2 + r)} "
        f"C {_f(cx - k)} {_f(y2 + r)} {_f(cx - r)} {_f(y2 + k)} {_f(cx - r)} {_f(y2)} Z"
    )


def _spread_labels(wanted: list[float], gap: float, low: float, high: float) -> list[float]:
    """Rotulos lo mas cerca posible de su pieza, sin pisarse."""
    placed: list[float] = []
    for y in wanted:
        placed.append(max(y, low, placed[-1] + gap if placed else low))
    overflow = placed[-1] - high if placed else 0.0
    if overflow > 0:
        placed[-1] -= overflow
        for index in range(len(placed) - 2, -1, -1):
            placed[index] = min(placed[index], placed[index + 1] - gap)
    return placed


@dataclass(frozen=True)
class _Piece:
    section: Section
    circ: float  # contorno maximo (cm)
    length: float  # largo sobre el tejido (cm)

    @property
    def diameter(self) -> float:
        return self.circ / pi


def _pieces(pattern: Pattern) -> dict[str, _Piece]:
    gauge = resolve_gauge(pattern.params)
    out: dict[str, _Piece] = {}
    for section in pattern.sections:
        top = section.meta.get("max_stitches", section.end_stitches)
        rows = section.meta.get("row_count", len(section.steps))
        out[section.id] = _Piece(section, gauge.cm_for_stitches(top), gauge.cm_for_rows(rows))
    return out


def render_toy_svg(pattern: Pattern, lang: str) -> str:
    pieces = _pieces(pattern)
    if "ball" in pieces:
        return _render_ball(pattern, pieces, lang)
    head, body = pieces["head"], pieces["body"]
    gauge = resolve_gauge(pattern.params)
    craft = "crochet" if pattern.spec.tecnica.value == "crochet" else "knit"
    figure = pattern.meta.title_key.removeprefix("title.toy_")

    # Geometria en cm, origen en la base del cuerpo y eje y hacia arriba.
    hd = head.diameter
    bw = body.diameter
    neck = gauge.cm_for_stitches(body.section.end_stitches) / pi
    base_units = body.section.meta.get("base_units", 0) * (1 if craft == "crochet" else 2)
    bh = 0.9 * (body.length - gauge.cm_for_rows(base_units))
    head_cy = bh + hd / 2 - 0.1 * hd
    top_cm = head_cy + hd / 2
    ear = pieces.get("ear")
    ear_top = top_cm
    if ear is not None:
        if figure == "bunny":
            ear_top = head_cy + hd / 2 - 0.1 * hd + ear.length
        elif figure == "cat":
            ear_top = head_cy + hd * 0.3 + ear.length * 0.9
        else:
            ear_top = head_cy + hd * 0.36 + ear.diameter / 2
    tail = pieces.get("tail")
    half_w = max(bw / 2 + 0.8 * pieces["arm"].diameter, hd / 2)
    if tail is not None and figure == "cat":
        half_w = max(half_w, bw * 0.45 + tail.length * 0.6)
    leg_d = pieces["leg"].diameter
    bottom_cm = -leg_d * 0.25
    span_h = max(ear_top, top_cm) - bottom_cm
    scale = min((BOTTOM - TOP - 30) / span_h, FIG_W / (2 * half_w))
    base_y = BOTTOM - 15 - (0 - bottom_cm) * scale

    def X(cm: float) -> float:
        return FIG_CX + cm * scale

    def Y(cm: float) -> float:
        return base_y - cm * scale

    back: list[str] = []
    front: list[str] = []
    anchors: list[tuple[float, float, Section]] = []

    # Orejas (detras de la cabeza).
    if ear is not None:
        for side in (-1, 1):
            if figure == "bunny":
                w = ear.circ / 2
                cx = side * hd * 0.2
                cy = head_cy + hd / 2 - 0.1 * hd + ear.length / 2
                back.append(
                    shape_path(
                        _ellipse(X(cx), Y(cy), w / 2 * scale, ear.length / 2 * scale), fill=FILL
                    )
                )
                back.append(
                    shape_path(
                        _ellipse(X(cx), Y(cy), w / 4 * scale, ear.length * 0.36 * scale),
                        fill=FILL_ALT,
                        width=1,
                    )
                )
                anchor_y = cy + ear.length * 0.3
            elif figure == "cat":
                w = ear.circ / 2
                bx, by = side * hd * 0.3, head_cy + hd * 0.3
                tip = (bx + side * w * 0.15, by + ear.length * 0.9)
                d = (
                    f"M {_f(X(bx - w / 2))} {_f(Y(by))} L {_f(X(tip[0]))} {_f(Y(tip[1]))} "
                    f"L {_f(X(bx + w / 2))} {_f(Y(by))} Z"
                )
                back.append(shape_path(d, fill=FILL))
                cx, anchor_y = bx, by + ear.length * 0.5
            else:
                cx = side * hd * 0.36
                cy = head_cy + hd * 0.36
                back.append(
                    f'<circle cx="{_f(X(cx))}" cy="{_f(Y(cy))}" r="{_f(ear.diameter / 2 * scale)}" fill="{FILL}" stroke="{STROKE}" stroke-width="2"/>'
                )
                back.append(
                    f'<circle cx="{_f(X(cx))}" cy="{_f(Y(cy))}" r="{_f(ear.diameter / 4 * scale)}" fill="{FILL_ALT}" stroke="none"/>'
                )
                anchor_y = cy + ear.diameter * 0.35
            if side == 1:
                anchors.append((X(cx), Y(anchor_y), ear.section))

    # Cola (asoma al costado, detras del cuerpo).
    if tail is not None:
        if figure == "cat":
            x0, y0 = bw * 0.3, bh * 0.15
            x1, y1 = bw * 0.45 + tail.length * 0.6, bh * 0.15 + tail.length * 0.5
            w = tail.diameter * scale
            d = (
                f"M {_f(X(x0))} {_f(Y(y0))} C {_f(X(x1))} {_f(Y(y0))} "
                f"{_f(X(x1))} {_f(Y(y0))} {_f(X(x1))} {_f(Y(y1))}"
            )
            back.append(
                f'<path d="{d}" fill="none" stroke="{STROKE}" stroke-width="{_f(w + 4)}" stroke-linecap="round"/>'
            )
            back.append(
                f'<path d="{d}" fill="none" stroke="{FILL}" stroke-width="{_f(w)}" stroke-linecap="round"/>'
            )
            anchors.append((X(x1), Y(y1), tail.section))
        else:
            cx, cy = bw * 0.5, bh * 0.18
            back.append(
                f'<circle cx="{_f(X(cx))}" cy="{_f(Y(cy))}" r="{_f(tail.diameter / 2 * scale)}" fill="{FILL}" stroke="{STROKE}" stroke-width="2"/>'
            )
            anchors.append((X(cx + tail.diameter * 0.3), Y(cy), tail.section))

    # Brazos (detras del cuerpo, colgando de los costados).
    arm = pieces["arm"]
    aw = arm.diameter
    for side in (-1, 1):
        cx = side * (neck / 2 + aw * 0.45)
        top = bh - aw * 0.2
        length = arm.length * 0.95
        back.append(shape_path(_capsule(X(cx), Y(top), aw * scale, length * scale), fill=FILL))
        if side == 1:
            anchors.append((X(cx + aw * 0.3), Y(top - length * 0.6), arm.section))

    # Cuerpo: pera de la base al cuello.
    left = (
        f"M {_f(X(0))} {_f(Y(0))} "
        f"C {_f(X(-bw * 0.55))} {_f(Y(0))} {_f(X(-bw * 0.6))} {_f(Y(bh * 0.55))} {_f(X(-neck / 2))} {_f(Y(bh))} "
        f"L {_f(X(neck / 2))} {_f(Y(bh))} "
        f"C {_f(X(bw * 0.6))} {_f(Y(bh * 0.55))} {_f(X(bw * 0.55))} {_f(Y(0))} {_f(X(0))} {_f(Y(0))} Z"
    )
    front.append(shape_path(left, fill=FILL))
    anchors.append((X(bw * 0.12), Y(bh * 0.4), body.section))

    # Cabeza.
    front.append(
        f'<circle cx="{_f(X(0))}" cy="{_f(Y(head_cy))}" r="{_f(hd / 2 * scale)}" fill="{FILL}" stroke="{STROKE}" stroke-width="2"/>'
    )
    anchors.append((X(hd * 0.3), Y(head_cy + hd * 0.22), head.section))
    muzzle = pieces.get("muzzle")
    eye_y = head_cy - hd * 0.02
    if muzzle is not None:
        my = head_cy - hd * 0.2
        front.append(
            shape_path(
                _ellipse(
                    X(0), Y(my), muzzle.diameter * 0.55 * scale, muzzle.diameter * 0.42 * scale
                ),
                fill=FILL_ALT,
            )
        )
        front.append(
            shape_path(
                _ellipse(
                    X(0), Y(my + muzzle.diameter * 0.12), hd * 0.06 * scale, hd * 0.04 * scale
                ),
                fill=TEXT,
                stroke=TEXT,
                width=1,
            )
        )
        anchors.append((X(muzzle.diameter * 0.3), Y(my - muzzle.diameter * 0.15), muzzle.section))
    else:
        front.append(
            shape_path(
                _ellipse(X(0), Y(head_cy - hd * 0.12), hd * 0.04 * scale, hd * 0.03 * scale),
                fill=TEXT,
                stroke=TEXT,
                width=1,
            )
        )
    for side in (-1, 1):
        front.append(
            f'<circle cx="{_f(X(side * hd * 0.2))}" cy="{_f(Y(eye_y))}" r="{_f(max(2.5, hd * 0.05 * scale))}" fill="{TEXT}"/>'
        )

    # Piernas: se ven las plantas, adelante en la base.
    leg = pieces["leg"]
    for side in (-1, 1):
        cx = side * bw * 0.26
        front.append(
            shape_path(
                _ellipse(X(cx), Y(leg_d * 0.3), leg_d / 2 * scale, leg_d * 0.55 * scale), fill=FILL
            )
        )
        front.append(
            shape_path(
                _ellipse(X(cx), Y(leg_d * 0.25), leg_d * 0.25 * scale, leg_d * 0.3 * scale),
                fill=FILL_ALT,
                width=1,
            )
        )
        if side == 1:
            anchors.append((X(cx + leg_d * 0.3), Y(leg_d * 0.3), leg.section))

    return _finish(pattern, lang, craft, anchors, back, front, top_cm, half_w, X, Y)


def _finish(
    pattern: Pattern,
    lang: str,
    craft: str,
    anchors: list[tuple[float, float, Section]],
    back: list[str],
    front: list[str],
    top_cm: float,
    half_w: float,
    X: Callable[[float], float],
    Y: Callable[[float], float],
) -> str:
    """Rotulos, altura y documento: comun a todas las formas de juguete."""
    # Rotulos: columna a la derecha, en el orden vertical de las piezas.
    rows_word = "schematic.toy_info." + craft
    labels: list[str] = []
    anchors.sort(key=lambda item: item[1])
    spots = _spread_labels([a[1] for a in anchors], 42.0, TOP + 10, BOTTOM - 20)
    for (ax, ay, section), ly in zip(anchors, spots, strict=True):
        name = t(section.name_key, lang)
        info = t(
            rows_word,
            lang,
            sts=section.meta.get("max_stitches", 0),
            rows=section.meta.get("row_count", 0),
        )
        labels.append(f'<circle cx="{_f(ax)}" cy="{_f(ay)}" r="2.6" fill="{STROKE}"/>')
        labels.append(
            f'<path d="M {_f(ax)} {_f(ay)} L {_f(LABEL_X - 30)} {_f(ly)} L {_f(LABEL_X - 6)} {_f(ly)}" '
            f'fill="none" stroke="{STROKE}" stroke-width="0.8"/>'
        )
        labels.append(
            label(LABEL_X, ly + 4, name, size=12, anchor="start", weight="700", color=TEXT)
        )
        labels.append(label(LABEL_X, ly + 19, info, size=10, anchor="start", color=TEXT_SOFT))

    # Altura (a la izquierda, fuera del dibujo).
    height = next((m.value_cm for m in pattern.measurements if m.key == "toy_height"), top_cm)
    units = pattern.params.unidades
    shown = height / 2.54 if units == "in" else height
    value = f"{round_half_up(shown * 2) / 2:g} {units}"  # como la ficha tecnica
    dim_x = X(-half_w) - 28
    dims = dim_v(
        Y(top_cm), Y(0), dim_x, (t("measure.height", lang), value), side="left", extension=12
    )

    title = t(pattern.meta.title_key, lang)
    unit = t("unit.cm" if units == "cm" else "unit.in", lang)
    parts = [
        *title_block(WIDTH, 42, title, t("schematic.measures_in", lang, unit=unit)),
        *back,
        *front,
        *dims,
        *labels,
        caption(WIDTH, HEIGHT - 20, t("schematic.toy_note", lang)),
    ]
    return svg_document(WIDTH, HEIGHT, title, t("pattern.schematic", lang), parts)


def _render_ball(pattern: Pattern, pieces: dict[str, _Piece], lang: str) -> str:
    """Bolita de frente: la esfera, orejas arriba, patitas abajo y la cola
    asomando al costado. Mismas proporciones que las piezas tejidas."""
    ball = pieces["ball"]
    craft = "crochet" if pattern.spec.tecnica.value == "crochet" else "knit"
    figure = pattern.meta.title_key.removeprefix("title.toy_")
    d = 2 * ball.length / pi  # la esfera mide medio contorno de alto
    r = d / 2
    cy = r
    ear, foot, tail = pieces.get("ear"), pieces.get("foot"), pieces.get("tail")
    ear_top = d
    if ear is not None:
        ear_top = cy + r * 0.75 + (ear.length if figure != "bear" else ear.diameter * 0.6)
    foot_d = foot.diameter if foot is not None else 0.0
    half_w = r + (tail.length * 0.7 if tail is not None else 0.0)
    bottom_cm = -foot_d * 0.3
    scale = min((BOTTOM - TOP - 30) / (max(ear_top, d) - bottom_cm), FIG_W / (2 * half_w))
    base_y = BOTTOM - 15 + bottom_cm * scale

    def X(cm: float) -> float:
        return FIG_CX + cm * scale

    def Y(cm: float) -> float:
        return base_y - cm * scale

    back: list[str] = []
    front: list[str] = []
    anchors: list[tuple[float, float, Section]] = []
    if ear is not None:
        for side in (-1, 1):
            bx, by = side * r * 0.5, cy + r * 0.75
            if figure == "cat":
                w = ear.circ / 2
                tip = (bx + side * w * 0.15, by + ear.length)
                path = f"M {_f(X(bx - w / 2))} {_f(Y(by - r * 0.1))} L {_f(X(tip[0]))} {_f(Y(tip[1]))} L {_f(X(bx + w / 2))} {_f(Y(by - r * 0.1))} Z"
                back.append(shape_path(path, fill=FILL))
                anchor_y = by + ear.length * 0.5
            elif figure == "bunny":
                w = ear.circ / 2
                ey = by + ear.length / 2
                back.append(
                    shape_path(
                        _ellipse(X(bx * 0.6), Y(ey), w / 2 * scale, ear.length / 2 * scale),
                        fill=FILL,
                    )
                )
                back.append(
                    shape_path(
                        _ellipse(X(bx * 0.6), Y(ey), w / 4 * scale, ear.length * 0.36 * scale),
                        fill=FILL_ALT,
                        width=1,
                    )
                )
                bx, anchor_y = bx * 0.6, ey + ear.length * 0.3
            else:
                er = ear.diameter / 2
                back.append(
                    f'<circle cx="{_f(X(bx))}" cy="{_f(Y(by + er * 0.4))}" r="{_f(er * scale)}" fill="{FILL}" stroke="{STROKE}" stroke-width="2"/>'
                )
                back.append(
                    f'<circle cx="{_f(X(bx))}" cy="{_f(Y(by + er * 0.4))}" r="{_f(er / 2 * scale)}" fill="{FILL_ALT}" stroke="none"/>'
                )
                anchor_y = by + er
            if side == 1:
                anchors.append((X(bx), Y(anchor_y), ear.section))
    if tail is not None:
        if figure == "cat":
            x0, x1 = r * 0.8, r + tail.length * 0.7
            back.append(
                shape_path(
                    _ellipse(
                        X((x0 + x1) / 2),
                        Y(r * 0.55),
                        (x1 - x0) / 2 * scale,
                        tail.diameter / 2 * scale,
                    ),
                    fill=FILL,
                )
            )
            anchors.append((X(x1 - tail.diameter * 0.3), Y(r * 0.55), tail.section))
        else:
            tr = tail.diameter / 2
            back.append(
                f'<circle cx="{_f(X(r * 0.92))}" cy="{_f(Y(r * 0.5))}" r="{_f(tr * scale)}" fill="{FILL}" stroke="{STROKE}" stroke-width="2"/>'
            )
            anchors.append((X(r * 0.92 + tr * 0.5), Y(r * 0.5), tail.section))
    front.append(
        f'<circle cx="{_f(X(0))}" cy="{_f(Y(cy))}" r="{_f(r * scale)}" fill="{FILL}" stroke="{STROKE}" stroke-width="2"/>'
    )
    anchors.append((X(r * 0.45), Y(cy + r * 0.25), ball.section))
    for side in (-1, 1):
        front.append(
            f'<circle cx="{_f(X(side * r * 0.3))}" cy="{_f(Y(cy + r * 0.05))}" r="{_f(max(2.5, r * 0.07 * scale))}" fill="{TEXT}"/>'
        )
    front.append(
        shape_path(
            _ellipse(X(0), Y(cy - r * 0.12), r * 0.05 * scale, r * 0.035 * scale),
            fill=TEXT,
            stroke=TEXT,
            width=1,
        )
    )
    if foot is not None:
        for side in (-1, 1):
            fx = side * r * 0.4
            front.append(
                shape_path(
                    _ellipse(X(fx), Y(foot_d * 0.15), foot_d / 2 * scale, foot_d * 0.4 * scale),
                    fill=FILL,
                )
            )
            if side == 1:
                anchors.append((X(fx + foot_d * 0.3), Y(foot_d * 0.15), foot.section))
    return _finish(pattern, lang, craft, anchors, back, front, max(ear_top, d), half_w, X, Y)


def render_round_chart_svg(pattern: Pattern, section_id: str, lang: str) -> str | None:
    """Grafico de simbolos de las vueltas de aumento de una pieza al crochet
    (anillo magico y aumentos repartidos), como el de los motivos: cada
    simbolo sale del punto donde se teje. Las vueltas parejas y las
    disminuciones siguen en el texto."""
    from engine.document import growth_rounds
    from engine.stitches.kinds import StitchKind
    from render.crochet_chart import draw_rounds
    from render.crochet_chart import legend as chart_legend

    section = next((s for s in pattern.sections if s.id == section_id), None)
    if section is None or not section.steps:
        return None
    grow = growth_rounds(section.steps)
    width, size = 900.0, 640.0
    fills = [FILL if index % 2 else FILL_ALT for index in range(len(grow))]
    parts, used = draw_rounds(
        grow,
        [StitchKind.SC] * len(grow),
        [False] * len(grow),
        fills,
        width / 2,
        110 + size / 2,
        size / 2,
    )
    y = 110 + size + 40
    parts.append(label(width / 2, y, t("chart.round_inc", lang), size=12, color=TEXT_SOFT))
    parts += chart_legend(used, lang, 90, y + 44, width - 180)
    title = t(section.name_key, lang)
    head = title_block(width, 42, title, t("doc.round_chart_sub", lang, n=len(grow)))
    return svg_document(width, y + 110, title, t("doc.charts", lang), head + parts)
