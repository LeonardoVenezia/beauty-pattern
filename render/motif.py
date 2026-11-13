"""Grafico de simbolos del motivo de crochet: una franja por vuelta con el
color de su banda y un simbolo por punto. Sale de las vueltas verificadas."""

from __future__ import annotations

import math

from engine.garments.motif import _SOLID, _SPACED
from engine.i18n import t
from engine.ir import Pattern, Step
from engine.spec import MotifStitch
from engine.stitches.kinds import StitchKind
from render.crochet_chart import draw_rounds, start_angle
from render.crochet_chart import legend as chart_legend
from render.draw import STROKE, TEXT_SOFT, _f, caption, label, svg_document, title_block
from render.granny import _hex

WIDTH, HEIGHT = 900.0, 800.0
# Legibilidad (mucha gente que teje es mayor): si un simbolo quedaria de menos
# de _MIN_PX, se dibuja ampliado un sector en vez del motivo entero.
_MIN_PX = 9.0


def _too_small(steps: tuple[Step, ...], radius: float) -> bool:
    # ponytail: estimacion con un alto medio de 2.2 pb por vuelta; medir el
    # dibujo real si hace falta mas precision.
    unit = radius / (1.2 + 2.2 * len(steps))
    slot = 2 * math.pi * 0.9 * radius / max(s.stitch_count_end for s in steps)
    return min(unit, slot) < _MIN_PX


def render_motif_svg(pattern: Pattern, lang: str) -> str:
    design = pattern.spec.motivo
    steps = pattern.sections[0].steps
    colors = list(pattern.materials.colors)
    square_from = next(
        (s.number for s in steps if any(getattr(i, "ops", ()) and i.ops[0].kind.value == "square_turn" for i in s.items)),
        None,
    )
    band = 0
    bands: list[int] = []
    for step in steps:  # banda de cada vuelta (la nota marca el comienzo)
        if step.note_params:
            band = int(dict(step.note_params).get("band", band + 1)) - 1
        bands.append(band)
    squares = [square_from is not None and step.number >= square_from for step in steps]
    bases, fills = [], []
    for index in range(len(steps)):
        stitch = design.bandas[bands[index]].punto if design else MotifStitch.DC
        kind = _SOLID.get(stitch) or _SPACED.get(stitch, StitchKind.DC)
        bases.append(StitchKind.DC if squares[index] and stitch not in _SOLID else kind)
        color_index = design.bandas[bands[index]].color if design else None
        fills.append(
            _hex(colors[color_index], color_index)
            if color_index is not None and color_index < len(colors)
            else _hex("", index)
        )
    size = 440.0
    cx, cy = WIDTH / 2, 118.0 + size / 2
    spaced_ring = bool(design) and design.bandas[0].punto in _SPACED
    symmetry = design.simetria if design else 8
    radius, span = size / 2, 2 * math.pi
    if _too_small(steps, radius):
        # Motivo grande: se dibuja ampliado un sector (>= 1/4) y se repite.
        span = 2 * math.pi * math.ceil(symmetry / 4) / symmetry
        # Encuadre: caja del sector (centro + borde exterior) con radio 1.
        start = start_angle(steps, bases, squares, spaced_ring)
        square = any(squares)
        points = [(0.0, 0.0)]
        for k in range(49):
            a = start - span * k / 48
            reach = 1 / max(abs(math.cos(a)), abs(math.sin(a))) if square else 1.0
            points.append((reach * math.cos(a), reach * math.sin(a)))
        xs, ys = [x for x, _ in points], [y for _, y in points]
        radius = min((WIDTH - 140) / (max(xs) - min(xs)), size / (max(ys) - min(ys)))
        cx = WIDTH / 2 - radius * (max(xs) + min(xs)) / 2
        cy = 118.0 - radius * min(ys)
    parts, used = draw_rounds(steps, bases, squares, fills, cx, cy, radius, spaced_ring=spaced_ring, span=span)
    if span < 2 * math.pi:
        parts.append(label(WIDTH / 2, 104, t("schematic.motif_partial", lang), size=11, color=TEXT_SOFT))
    measure = pattern.measurements[0]
    unit = t(f"unit.{pattern.params.unidades}", lang)
    shown = measure.value_cm / 2.54 if pattern.params.unidades == "in" else measure.value_cm
    y_dim = 118.0 + size + 22
    partial = span < 2 * math.pi
    left = WIDTH / 2 - size / 2
    if not partial:
        parts.append(f'<line x1="{_f(left)}" y1="{_f(y_dim)}" x2="{_f(left + size)}" y2="{_f(y_dim)}" stroke="{STROKE}"/>')
    size_text = f"{round(shown * 2) / 2:g} {unit}"
    if partial:
        size_text = t("schematic.motif_total", lang, size=size_text)
    parts.append(label(WIDTH / 2, y_dim + 18, size_text, size=12, weight="700"))
    if colors:
        legend = "   ".join(f"{chr(65 + i)}: {name}" for i, name in enumerate(colors))
        parts.append(label(WIDTH / 2, y_dim + 36, legend, size=11, color=TEXT_SOFT))
    parts += chart_legend(used, lang, 90, y_dim + 74, WIDTH - 180)
    title = t(pattern.meta.title_key, lang)
    head = title_block(WIDTH, 42, title, t("schematic.motif_note", lang, n=len(steps), s=symmetry))
    tail = [caption(WIDTH, HEIGHT - 20, t("schematic.caption", lang))]
    return svg_document(WIDTH, HEIGHT, title, t("pattern.schematic", lang), head + parts + tail)
