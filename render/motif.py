"""Diagrama del motivo de crochet: una franja por vuelta, con el color de su
banda y los rayos de la simetria. Sale de las vueltas verificadas de la IR."""

from __future__ import annotations

import math

from engine.i18n import t
from engine.ir import Pattern
from render.draw import STROKE, TEXT, TEXT_SOFT, _f, caption, label, svg_document, title_block
from render.granny import _hex

WIDTH, HEIGHT = 900.0, 720.0


def render_motif_svg(pattern: Pattern, lang: str) -> str:
    design = pattern.spec.motivo
    steps = pattern.sections[0].steps
    colors = list(pattern.materials.colors)
    square_from = next(
        (s.number for s in steps if any(getattr(i, "ops", ()) and i.ops[0].kind.value == "square_turn" for i in s.items)),
        None,
    )
    size = 440.0
    cx, cy = WIDTH / 2, 130.0 + size / 2
    band_w = size / 2 / max(1, len(steps))
    parts: list[str] = []
    band = 0
    bands: list[int] = []
    for step in steps:  # banda de cada vuelta (la nota marca el comienzo)
        if step.note_params:
            band = int(dict(step.note_params).get("band", band + 1)) - 1
        bands.append(band)
    for index in range(len(steps), 0, -1):
        r = index * band_w
        color_index = design.bandas[bands[index - 1]].color if design else None
        fill = _hex(colors[color_index], color_index) if color_index is not None and color_index < len(colors) else _hex("", index)
        if square_from is not None and index >= square_from:
            parts.append(
                f'<rect x="{_f(cx - r)}" y="{_f(cy - r)}" width="{_f(2 * r)}" height="{_f(2 * r)}" '
                f'fill="{fill}" stroke="{STROKE}" stroke-width="0.8"/>'
            )
        else:
            parts.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="{fill}" stroke="{STROKE}" stroke-width="0.8"/>')
    symmetry = design.simetria if design else 8
    reach = (square_from - 1 if square_from else len(steps)) * band_w
    for k in range(symmetry):
        angle = 2 * math.pi * k / symmetry - math.pi / 2
        parts.append(
            f'<line x1="{_f(cx)}" y1="{_f(cy)}" x2="{_f(cx + reach * math.cos(angle))}" '
            f'y2="{_f(cy + reach * math.sin(angle))}" stroke="{STROKE}" stroke-width="0.6" opacity="0.5"/>'
        )
    for index in range(1, len(steps) + 1):
        parts.append(label(cx + (index - 0.5) * band_w, cy + 4, str(index), size=9, color=TEXT))
    measure = pattern.measurements[0]
    unit = t(f"unit.{pattern.params.unidades}", lang)
    shown = measure.value_cm / 2.54 if pattern.params.unidades == "in" else measure.value_cm
    y_dim = cy + size / 2 + 26
    parts.append(f'<line x1="{_f(cx - size / 2)}" y1="{_f(y_dim)}" x2="{_f(cx + size / 2)}" y2="{_f(y_dim)}" stroke="{STROKE}"/>')
    parts.append(label(cx, y_dim + 18, f"{round(shown * 2) / 2:g} {unit}", size=12, weight="700"))
    if colors:
        legend = "   ".join(f"{chr(65 + i)}: {name}" for i, name in enumerate(colors))
        parts.append(label(cx, HEIGHT - 52, legend, size=11, color=TEXT_SOFT))
    title = t(pattern.meta.title_key, lang)
    head = title_block(WIDTH, 42, title, t("schematic.motif_note", lang, n=len(steps), s=symmetry))
    tail = [caption(WIDTH, HEIGHT - 20, t("schematic.caption", lang))]
    return svg_document(WIDTH, HEIGHT, title, t("pattern.schematic", lang), head + parts + tail)
