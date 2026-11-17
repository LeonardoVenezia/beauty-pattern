"""Esquemas de gorros por estilo, pasamontanas, vincha, mitones sin dedos,
polainas, escarpines y pantuflas (D038).

Cada pieza se dibuja con su perfil real, vuelta por vuelta, a partir de los
conteos verificados de la IR: el ancho de cada vuelta es pts / densidad (la
mitad si es en redondo: la pieza apoyada plana) y el alto, vueltas / densidad.
Asi un ala que se abre, una boina que se ensancha o la cuna del pulgar se ven
como son. Las piezas chicas (orejeras, pulgar, cana, lazos) van al costado.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.i18n import t
from engine.ir import Pattern, Section
from engine.spec import resolve_gauge
from render.draw import (
    FILL,
    STROKE,
    STROKE_SOFT,
    TEXT,
    TEXT_SOFT,
    _f,
    caption,
    dashed_line,
    dim_h,
    dim_v,
    label,
    shape_path,
    svg_document,
    title_block,
)

WIDTH, HEIGHT = 900.0, 720.0
TOP = 120.0
BOTTOM = 640.0

# Familia (sin el prefijo crochet_) -> (secciones de la pieza principal,
# dibujar de arriba hacia abajo en el orden tejido).
_MAIN: dict[str, tuple[tuple[str, ...], bool]] = {
    "hat": (("brim", "body", "crown"), False),
    "hat_slouchy": (("brim", "body", "crown"), False),
    "hat_beret": (("brim", "body", "crown"), False),
    "hat_earflap": (("brim", "body", "crown"), False),
    "hat_bucket": (("crown", "body", "brim"), True),
    "hat_brimmed": (("crown", "body", "brim"), True),
    "hat_bonnet": (("face", "back"), True),
    "balaclava": (("neck", "head", "face_opening", "top"), False),
    "headband": (("headband",), True),
    "fingerless_mitts": (("cuff", "thumb_gusset", "hand", "top"), False),
    "leg_warmers": (("cuff_top", "leg", "cuff_bottom"), True),
    "booties": (("toe", "foot", "heel"), True),
    "slippers": (("sole", "toe"), False),
}
# Las de crochet se tejen desde la coronilla: arriba lo primero.
_CROCHET_TOP_DOWN = {"hat", "hat_slouchy", "hat_beret", "hat_earflap"}


def supports(family: str) -> bool:
    """El gorro clasico de dos agujas conserva su dibujo propio (schematic.py)."""
    return family != "hat" and family.removeprefix("crochet_") in _MAIN


@dataclass(frozen=True)
class _Band:
    section: Section
    widths: list[float]  # cm, una por vuelta
    height: float  # cm


def _bands(pattern: Pattern, ids: tuple[str, ...], top_down: bool, *, halve_flat: bool) -> list[_Band]:
    gauge = resolve_gauge(pattern.params)
    by_id = {s.id: s for s in pattern.sections}
    bands: list[_Band] = []
    for sid in ids:
        section = by_id.get(sid)
        if section is None or not section.steps:
            continue
        halve = section.mode == "round" or halve_flat or section.id == "face_opening"
        counts = [step.stitch_count_end for step in section.steps if step.stitch_count_end > 0]
        if section.start_stitches:
            counts.insert(0, section.start_stitches)
        if section.id == "face_opening":  # la abertura se ve en el frente: el contorno sigue entero
            counts = [section.start_stitches] * len(counts)
        widths = [gauge.cm_for_stitches(c) / (2 if halve else 1) for c in counts] or [1.0]
        rows = section.meta.get("row_count", len(section.steps))
        bands.append(_Band(section, widths, gauge.cm_for_rows(max(rows, 1))))
    if top_down:
        return bands
    return [_Band(b.section, list(reversed(b.widths)), b.height) for b in reversed(bands)]


def _outline(bands: list[_Band], cx: float, top: float, k: float) -> tuple[str, list[float]]:
    """Contorno simetrico (de arriba hacia abajo) y la y de cada limite."""
    right: list[tuple[float, float]] = []
    edges = [top]
    y = top
    for band in bands:
        n = len(band.widths)
        for i, w in enumerate(band.widths):
            yy = y + band.height * k * (i / (n - 1) if n > 1 else 0.5)
            right.append((cx + w * k / 2, yy))
        y += band.height * k
        edges.append(y)
    if right:
        right.insert(0, (right[0][0], top))
        right.append((right[-1][0], y))
    left = [(2 * cx - x, yy) for x, yy in reversed(right)]
    pts = right + left
    d = "M " + " L ".join(f"{_f(x)} {_f(yy)}" for x, yy in pts) + " Z"
    return d, edges


def _fmt(pattern: Pattern, cm: float) -> str:
    if pattern.params.unidades == "in":
        return f"{cm / 2.54:.1f} in"
    return f"{cm:.1f} cm"


def _piece(
    parts: list[str],
    pattern: Pattern,
    lang: str,
    bands: list[_Band],
    box: tuple[float, float, float, float],
    *,
    title: str,
    note: str | None,
    detail: bool,
) -> None:
    x0, y0, bw, bh = box
    if not bands:
        return
    total_h = sum(b.height for b in bands)
    widest = max(max(b.widths) for b in bands)
    pad_side = 150.0 if detail else 30.0
    k = min((bw - pad_side) / max(widest, 1e-6), (bh - 70.0) / max(total_h, 1e-6))
    cx = x0 + (bw - (110.0 if detail else 0.0)) / 2 + (40.0 if detail else 0.0)
    top = y0 + (52.0 if detail else 30.0)
    d, edges = _outline(bands, cx, top, k)
    parts.append(label(cx, y0 + 12, title, size=13 if detail else 11, weight="700", color=TEXT))
    parts.append(shape_path(d, fill=FILL, stroke=STROKE, width=1.8))
    for edge in edges[1:-1]:
        half = widest * k / 2
        parts.append(dashed_line(cx - half, edge, cx + half, edge, color=STROKE_SOFT))
    bottom = edges[-1]
    if detail:
        for band, y_a, y_b in zip(bands, edges[:-1], edges[1:], strict=True):
            name = t(band.section.name_key, lang)
            left = cx - max(band.widths) * k / 2 - 10
            parts.append(label(left, (y_a + y_b) / 2 + 4, name, anchor="end", size=10, color=TEXT_SOFT))
            if y_b - y_a > 14:
                parts += dim_v(y_a, y_b, cx + widest * k / 2 + 18, (_fmt(pattern, band.height),), side="right", extension=-10, size=10)
        parts += dim_v(top, bottom, cx + widest * k / 2 + 100, (t("measure.length", lang), _fmt(pattern, total_h)), side="right", extension=-84, size=10)
        bottom_w = bands[-1].widths[-1]
        parts += dim_h(cx - bottom_w * k / 2, cx + bottom_w * k / 2, bottom + 30, (_fmt(pattern, bottom_w),), extension=-24, size=10)
        top_w = widest
        if abs(top_w - bottom_w) > 0.5:
            parts += dim_h(cx - top_w * k / 2, cx + top_w * k / 2, top - 8, (_fmt(pattern, top_w),), extension=8, size=10)
    else:
        w = max(max(b.widths) for b in bands)
        parts.append(label(cx, bottom + 14, f"{_fmt(pattern, w)} \u00d7 {_fmt(pattern, total_h)}", size=9, color=TEXT_SOFT))
    if note:
        parts.append(label(cx, bottom + (54 if detail else 27), note, size=10, color=TEXT_SOFT))


def _side_pieces(pattern: Pattern, main: set[str]) -> list[Section]:
    return [s for s in pattern.sections if s.id not in main and s.steps]


def render_accessory_svg(pattern: Pattern, lang: str) -> str:
    family = pattern.meta.family.removeprefix("crochet_")
    crochet = pattern.meta.family.startswith("crochet_")
    ids, top_down = _MAIN["booties" if family == "slippers" and crochet else family]
    if crochet and family in _CROCHET_TOP_DOWN:
        ids, top_down = tuple(s.id for s in pattern.sections if s.id in {"crown", "body", "brim"}), True
    flat_folded = family == "booties" or (family == "slippers" and crochet)
    bands = _bands(pattern, ids, top_down, halve_flat=flat_folded)
    side = _side_pieces(pattern, set(ids))
    main_w = WIDTH - 120 - (240 if side else 0)
    parts: list[str] = []
    title = t(pattern.meta.title_key, lang)
    note_key = f"acc.schematic.{family}"
    note = t(note_key, lang)
    _piece(parts, pattern, lang, bands, (60.0, TOP, main_w, BOTTOM - TOP), title=title, note=None if note == note_key else note, detail=True)
    if side:
        slot = (BOTTOM - TOP) / len(side)
        for index, section in enumerate(side):
            piece = _bands(pattern, (section.id,), True, halve_flat=False)
            two = "acc.note.make_two" in section.note_keys
            cut = t("acc.schematic.make_two" if two else "schematic.cut_one", lang)
            _piece(
                parts,
                pattern,
                lang,
                piece,
                (WIDTH - 280.0, TOP + index * slot, 240.0, slot),
                title=t(section.name_key, lang),
                note=cut,
                detail=False,
            )
    unit = t("unit.cm" if pattern.params.unidades == "cm" else "unit.in", lang)
    head = title_block(WIDTH, 42, title, t("schematic.measures_in", lang, unit=unit))
    tail = [caption(WIDTH, HEIGHT - 20, t("acc.schematic.caption", lang))]
    return svg_document(WIDTH, HEIGHT, title, t("pattern.schematic", lang), head + parts + tail)


__all__ = ["render_accessory_svg", "supports"]
