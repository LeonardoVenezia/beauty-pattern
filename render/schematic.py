"""Diagramas de piezas parametricos, derivados de la IR verificada.

Cada familia dibuja sus piezas reales usando medidas y perfiles de puntos de
la IR (no siluetas inventadas). El mismo SVG se usa en web y PDF.
Determinista: sin IA, sin inventar numeros.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from engine.i18n import t
from engine.ir import Pattern, Section
from engine.spec import resolve_gauge
from render.draw import (
    FILL,
    STROKE,
    STROKE_SOFT,
    TEXT,
    TEXT_SOFT,
    caption,
    clip_group,
    dashed_line,
    dim_h,
    dim_v,
    knit_texture,
    label,
    shape_path,
    svg_document,
    title_block,
)

WIDTH = 900.0
HEIGHT = 720.0
MARGIN_X = 60.0
TOP = 115.0
BOTTOM = 640.0

_PANEL_FAMILIES = {
    "scarf",
    "crochet_scarf",
    "shawl",
    "blanket",
    "flat_piece",
    "crochet_flat_piece",
}

ACCESSORY_FAMILIES = {
    *_PANEL_FAMILIES,
    "hat",
    "cowl",
    "socks",
    "mittens",
    "bag",
    "crochet_bag",
    "granny_square",
    "amigurumi",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _f(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _measure(pattern: Pattern, key: str) -> float | None:
    for m in pattern.measurements:
        if m.key == key:
            return m.value_cm
    return None


def _value(pattern: Pattern, key: str, default: float = 0.0) -> float:
    v = _measure(pattern, key)
    return v if v is not None else default


def _fmt(pattern: Pattern, cm: float) -> str:
    if pattern.params.unidades == "in":
        val = cm / 2.54
        return f"{val:.1f} in"
    return f"{cm:.1f} cm"


def _mname(lang: str, key: str) -> str:
    name = t(f"measure.{key}", lang)
    if name == f"measure.{key}":
        name = t(f"schematic.{key}", lang)
    if name.startswith(("measure.", "schematic.")):
        return key.replace("_", " ").capitalize()
    return name


def _section_by_id(pattern: Pattern, sid: str) -> Section | None:
    for s in pattern.sections:
        if s.id == sid:
            return s
    for s in pattern.sections:
        if s.id.startswith(sid):
            return s
    return None


def _section_length_cm(pattern: Pattern, section: Section) -> float:
    gauge = resolve_gauge(pattern.params)
    if section.target and section.target.dimension == "length":
        return section.target.target_cm
    rows = len(section.steps) if section.steps else int(section.meta.get("row_count", 0))
    if rows > 0:
        return gauge.cm_for_rows(rows)
    for key in (f"{section.id}_length", "length", "body_length", "sleeve_length"):
        v = _measure(pattern, key)
        if v is not None:
            return v
    return 10.0


def _width_cm(pattern: Pattern, stitches: int, mode: str) -> float:
    gauge = resolve_gauge(pattern.params)
    cm = gauge.cm_for_stitches(max(stitches, 0))
    return cm / 2.0 if mode == "round" else cm


def _profile(pattern: Pattern, section: Section) -> list[float]:
    """Anchos (cm) a lo largo de la seccion, de inicio a fin."""
    start = _width_cm(pattern, section.start_stitches, section.mode)
    if not section.steps:
        end = _width_cm(pattern, section.end_stitches or section.start_stitches, section.mode)
        return [start, end]
    vals = [start]
    vals.extend(_width_cm(pattern, st.stitch_count_end, section.mode) for st in section.steps)
    return vals


def _sample_profile(profile: Sequence[float], n: int) -> list[float]:
    if n <= 1:
        return [profile[-1] if profile else 1.0]
    if not profile:
        return [1.0] * n
    out: list[float] = []
    for i in range(n):
        pos = i * (len(profile) - 1) / (n - 1)
        lo = math.floor(pos)
        hi = min(lo + 1, len(profile) - 1)
        t = pos - lo
        out.append(profile[lo] * (1 - t) + profile[hi] * t)
    return out


def _max_w(profile: Sequence[float]) -> float:
    return max(profile) if profile else 1.0


def _path_from_profile(
    cx: float, y: float, w_px: float, h_px: float, prof_norm: Sequence[float]
) -> str:
    """Contorno simetrico: prof_norm en [0..1] relativo al ancho de dibujo, arriba->abajo."""
    n = len(prof_norm)
    right = []
    left = []
    for i, f in enumerate(prof_norm):
        yy = y + h_px * (i / (n - 1) if n > 1 else 1)
        half = w_px / 2 * max(f, 0.02)
        right.append((cx + half, yy))
        left.append((cx - half, yy))
    d = [f"M {_f(right[0][0])} {_f(right[0][1])}"]
    for px, py in right[1:]:
        d.append(f"L {_f(px)} {_f(py)}")
    for px, py in reversed(left):
        d.append(f"L {_f(px)} {_f(py)}")
    d.append("Z")
    return " ".join(d)


def _draw_piece(
    parts: list[str],
    pattern: Pattern,
    lang: str,
    *,
    title: str,
    profile_cm: Sequence[float],
    length_cm: float,
    x: float,
    y: float,
    box_w: float,
    box_h: float,
    piece_id: str,
    note: str | None = None,
    cut: str | None = None,
) -> tuple[float, float, float, float]:
    """Dibuja una pieza centrada en la caja (x,y,box_w,box_h). Devuelve bounds reales."""
    max_cm = max(max(profile_cm), 1e-6)
    # leave padding inside box for labels
    pad_x = 18.0
    pad_top = 22.0
    pad_bot = 8.0
    inner_w = max(box_w - 2 * pad_x, 20.0)
    inner_h = max(box_h - pad_top - pad_bot, 20.0)
    scale = min(inner_w / max_cm, inner_h / max(max(length_cm, 1e-6), 1e-6))
    # recompute
    draw_w = max_cm * scale
    draw_h = max(length_cm, 1e-6) * scale
    # center
    ox = x + (box_w - draw_w) / 2
    oy = y + pad_top
    cx = ox + draw_w / 2
    # resample
    steps_n = max(min(len(profile_cm), 120), 24)
    sampled = _sample_profile(profile_cm, steps_n)
    norm = [v / max_cm for v in sampled]
    path_d = _path_from_profile(cx, oy, draw_w, draw_h, norm)
    # clip + fill + subtle knit/crochet-free (clean like Valeria)
    clip_id = f"clip-{piece_id}"
    parts += clip_group(clip_id, f'<path d="{path_d}"/>', [
        f'<rect x="{_f(ox-2)}" y="{_f(oy-2)}" width="{_f(draw_w+4)}" height="{_f(draw_h+4)}" fill="{FILL}"/>',
        # fold line center
        dashed_line(cx, oy, cx, oy + draw_h, color="#e8d8c8"),
    ])
    parts.append(shape_path(path_d, fill="none", stroke=STROKE, width=1.6))
    # title
    parts.append(label(x + box_w / 2, y + 12, title, size=12, weight="700", color=TEXT))
    if cut:
        parts.append(label(x + box_w / 2, y + box_h - 2, cut, size=9, color=TEXT_SOFT))
    if note:
        parts.append(label(x + box_w / 2, oy + draw_h + 14, note, size=9, color=TEXT_SOFT))
    return ox, oy, draw_w, draw_h


def _add_dims(
    parts: list[str],
    pattern: Pattern,
    lang: str,
    ox: float,
    oy: float,
    dw: float,
    dh: float,
    width_cm: float | None,
    length_cm: float | None,
    *,
    w_key: str = "width",
    l_key: str = "length",
    bottom_width_cm: float | None = None,
    bottom_w_key: str | None = None,
) -> None:
    if width_cm is not None and width_cm > 0:
        parts += dim_h(ox, ox + dw, oy - 10, (_mname(lang, w_key), _fmt(pattern, width_cm)), extension=8)
    if bottom_width_cm is not None and bottom_w_key and abs((bottom_width_cm or 0) - (width_cm or 0)) > 0.3:
        parts += dim_h(ox, ox + dw, oy + dh + 28, (_mname(lang, bottom_w_key), _fmt(pattern, bottom_width_cm)), extension=-22)
    elif width_cm is not None and length_cm is not None:
        # bottom width label only if different? keep simple: show length on side
        pass
    if length_cm is not None and length_cm > 0:
        parts += dim_v(oy, oy + dh, ox + dw + 18, (_mname(lang, l_key), _fmt(pattern, length_cm)), side="right", extension=-14)


def _frame(pattern: Pattern, lang: str, parts: list[str], subtitle: str | None = None) -> str:
    title = t(pattern.meta.title_key, lang)
    if subtitle is None:
        unit = t("unit.cm" if pattern.params.unidades == "cm" else "unit.in", lang)
        garment_families = {
            "raglan_top_down", "drop_shoulder", "yoke", "set_in_sleeve",
            "cardigan", "vest", "flat", "set_in",
        }
        if pattern.meta.family in garment_families:
            subtitle = t("schematic.size_measures_in", lang, size=pattern.meta.size, unit=unit)
        else:
            subtitle = t("schematic.measures_in", lang, unit=unit)
    head = title_block(WIDTH, 42, title, subtitle)
    tail = [caption(WIDTH, HEIGHT - 20, t("schematic.caption", lang))]
    return svg_document(WIDTH, HEIGHT, title, t("pattern.schematic", lang), head + parts + tail)


# ---------------------------------------------------------------------------
# Simple rectangular/panel pieces (accessories, panels)
# ---------------------------------------------------------------------------


def _rect_piece_svg(
    pattern: Pattern,
    lang: str,
    *,
    piece_title: str,
    width_cm: float,
    length_cm: float,
    w_key: str,
    l_key: str,
    cut: str | None = None,
    extra: list[str] | None = None,
) -> str:
    box_w, box_h = 360.0, 420.0
    x = (WIDTH - box_w) / 2
    y = TOP + 20
    parts: list[str] = []
    profile = [width_cm, width_cm]
    ox, oy, dw, dh = _draw_piece(
        parts, pattern, lang,
        title=piece_title, profile_cm=profile, length_cm=length_cm,
        x=x, y=y, box_w=box_w, box_h=box_h, piece_id="p1", cut=cut,
    )
    _add_dims(parts, pattern, lang, ox, oy, dw, dh, width_cm, length_cm, w_key=w_key, l_key=l_key)
    if extra:
        parts.extend(extra)
    return _frame(pattern, lang, parts)


def _panel_svg(pattern: Pattern, lang: str) -> str:
    # find width/length-like measurements
    w = _measure(pattern, "width") or _measure(pattern, "diameter") or _measure(pattern, "circumference") or _measure(pattern, "size") or _measure(pattern, "head") or 20.0
    length_cm = _measure(pattern, "length") or _measure(pattern, "height") or _measure(pattern, "foot_length") or 20.0
    w_key = "width" if _measure(pattern, "width") is not None else ("diameter" if _measure(pattern, "diameter") is not None else ("circumference" if _measure(pattern, "circumference") is not None else "size"))
    l_key = "length" if _measure(pattern, "length") is not None else ("height" if _measure(pattern, "height") is not None else "foot_length")
    title = t(f"section.{pattern.meta.family}", lang)
    if title.startswith("section."):
        title = t(pattern.meta.title_key, lang)
    cut = t("schematic.cut_one", lang)
    return _rect_piece_svg(pattern, lang, piece_title=title, width_cm=w, length_cm=length_cm, w_key=w_key, l_key=l_key, cut=cut)


def _bag_svg(pattern: Pattern, lang: str) -> str:
    w = _value(pattern, "width", 30.0)
    length_cm = _value(pattern, "length", 30.0)
    cut = t("schematic.cut_one", lang)
    note = t("schematic.optional_handles", lang)
    if note.startswith("schematic."):
        note = "Asas opcionales (no incluidas)"
    # asas sugeridas (decorativas) para que el diagrama sea mas claro
    box_w, box_h = 360.0, 420.0
    bx = (WIDTH - box_w) / 2
    by = TOP + 20
    handle_parts: list[str] = []
    for _dx, sx in ((0.0, 0.32), (0.0, 0.68)):
        hx = bx + box_w * sx
        hy = by + 18
        handle_parts.append(
            f'<path d="M {_f(hx - 26)} {_f(hy)} C {_f(hx - 26)} {_f(hy - 42)}, '
            f'{_f(hx + 26)} {_f(hy - 42)}, {_f(hx + 26)} {_f(hy)}" '
            f'fill="none" stroke="{STROKE_SOFT}" stroke-width="3" stroke-dasharray="6 4"/>'
        )
    # linea de doblez
    handle_parts.append(
        dashed_line(bx + 40, by + box_h * 0.52, bx + box_w - 40, by + box_h * 0.52, color=STROKE_SOFT)
    )
    extra = [label(WIDTH / 2, BOTTOM + 18, note, size=10, color=TEXT_SOFT), *handle_parts]
    return _rect_piece_svg(
        pattern,
        lang,
        piece_title=t("title.bag", lang) if not t("title.bag", lang).startswith("title.") else "Bolso (cuerpo)",
        width_cm=w,
        length_cm=length_cm,
        w_key="width",
        l_key="length",
        cut=cut,
        extra=extra,
    )


def _granny_svg(pattern: Pattern, lang: str) -> str:
    side = _measure(pattern, "width") or _measure(pattern, "size") or _measure(pattern, "length") or 20.0
    return _rect_piece_svg(pattern, lang, piece_title=t("title.granny_square", lang) if not t("title.granny_square", lang).startswith("title.") else "Granny square", width_cm=side, length_cm=side, w_key="width", l_key="length", cut="Tejer 1 motivo")


# ---------------------------------------------------------------------------
# Garments: pieces from IR sections
# ---------------------------------------------------------------------------


def _garment_pieces(pattern: Pattern, lang: str) -> list[tuple[str, Section | None, str | None]]:
    fam = pattern.meta.family
    if fam in {"raglan_top_down", "yoke"}:
        return [
            ("Cuerpo", _section_by_id(pattern, "body"), "1 en redondo / 1 al doblar"),
            ("Manga", _section_by_id(pattern, "sleeve_left") or _section_by_id(pattern, "sleeve"), "Tejer 2"),
        ]
    if fam in {"drop_shoulder", "flat", "vest"}:
        return [
            ("Espalda", _section_by_id(pattern, "back"), "Tejer 1"),
            ("Delantero", _section_by_id(pattern, "front"), "Tejer 1"),
            ("Manga", _section_by_id(pattern, "sleeve_left") or _section_by_id(pattern, "sleeve"), "Tejer 2"),
        ]
    if fam == "cardigan":
        return [
            ("Espalda", _section_by_id(pattern, "back"), "Tejer 1"),
            ("Delantero", _section_by_id(pattern, "front_left") or _section_by_id(pattern, "front"), "Tejer 2"),
            ("Manga", _section_by_id(pattern, "sleeve_left") or _section_by_id(pattern, "sleeve"), "Tejer 2"),
        ]
    if fam in {"set_in_sleeve", "set_in"}:
        return [
            ("Espalda/Delantero", _section_by_id(pattern, "back") or _section_by_id(pattern, "body"), "Tejer 2"),
            ("Manga", _section_by_id(pattern, "sleeve_left") or _section_by_id(pattern, "sleeve"), "Tejer 2"),
        ]
    # fallback: main sections
    mains = [s for s in pattern.sections if s.steps and len(s.steps) > 3]
    return [(t(s.name_key, lang), s, None) for s in mains[:4]]


def _multi_piece_svg(pattern: Pattern, lang: str) -> str:
    pieces = _garment_pieces(pattern, lang)
    # filter valid
    valid = []
    for title, sec, cut in pieces:
        if sec is None:
            continue
        prof = _profile(pattern, sec)
        length = _section_length_cm(pattern, sec)
        if length <= 0 or not prof:
            continue
        valid.append((title, sec, cut, prof, length))
    if not valid:
        return _panel_svg(pattern, lang)

    cols = 2 if len(valid) >= 2 else 1
    rows = (len(valid) + cols - 1) // cols
    gap_x = 40.0
    gap_y = 30.0
    area_w = WIDTH - 2 * MARGIN_X
    area_h = BOTTOM - TOP - 20
    box_w = (area_w - gap_x * (cols - 1)) / cols
    box_h = (area_h - gap_y * (rows - 1)) / rows

    parts: list[str] = []
    for idx, (title, sec, cut, prof, length) in enumerate(valid):
        r = idx // cols
        c = idx % cols
        bx = MARGIN_X + c * (box_w + gap_x)
        by = TOP + r * (box_h + gap_y)
        # normalize profile: for round body show half-width panel
        ox, oy, dw, dh = _draw_piece(
            parts, pattern, lang,
            title=title, profile_cm=prof, length_cm=length,
            x=bx, y=by, box_w=box_w, box_h=box_h,
            piece_id=sec.id, cut=cut,
        )
        top_cm = prof[0]
        bot_cm = prof[-1]
        _add_dims(
            parts, pattern, lang, ox, oy, dw, dh,
            top_cm, length,
            w_key="width", l_key="length",
            bottom_width_cm=bot_cm, bottom_w_key="width",
        )
        # medidas especificas relevantes (ej. pulgar)
        for mk in ("thumb", "palm", "foot_length", "circumference", "diameter", "height"):
            mv = _measure(pattern, mk)
            if mv is None:
                continue
            # asociar si la pieza/medida se relaciona
            if mk == "thumb" and "thumb" not in sec.id:
                continue
            if mk == "palm" and "hand" not in sec.id and "thumb" in sec.id:
                continue
            if mk in {"thumb"}:
                parts += dim_v(
                    oy, oy + dh, ox - 18,
                    (_mname(lang, mk), _fmt(pattern, mv)),
                    side="left", extension=14,
                )
            elif mk in {"circumference", "diameter"} and sec.id in {"body", "brim", "crown", "leg", "foot"}:
                parts.append(label(ox + dw / 2, oy - 22, f"{_mname(lang, mk)}: {_fmt(pattern, mv)}", size=9, color=TEXT_SOFT))
        # annotate stitch counts
        parts.append(label(ox + dw / 2, oy + dh + 16, f"{sec.start_stitches} → {sec.end_stitches} p", size=9, color=TEXT_SOFT))
    return _frame(pattern, lang, parts)


# ---------------------------------------------------------------------------
# Hat/cowl/mittens/socks/amigurumi specifics
# ---------------------------------------------------------------------------


def _hat_svg(pattern: Pattern, lang: str) -> str:
    """El gorro como se ve apoyado plano: borde, cuerpo y corona en una sola
    silueta a escala, con la textura del punto (elastico = columnas) y cotas
    de cada parte. La corona se cierra pasando la hebra: copa redondeada."""
    parts_by_id = {sid: _section_by_id(pattern, sid) for sid in ("brim", "body", "crown")}
    lengths = {sid: (_section_length_cm(pattern, sec) if sec else 0.0) for sid, sec in parts_by_id.items()}
    total = sum(lengths.values()) or _value(pattern, "length", 22.0)
    circ = _measure(pattern, "circumference") or _value(pattern, "head", 50.0)
    flat = circ / 2
    scale = min(380 / flat, 400 / total)
    w, h = flat * scale, total * scale
    x, bottom = (WIDTH - w) / 2 - 40, TOP + 40 + h
    crown_h, brim_h = lengths["crown"] * scale, lengths["brim"] * scale
    shoulder = bottom - h + crown_h  # donde empieza la corona
    top = bottom - h
    outline = (
        f"M {_f(x)} {_f(bottom)} L {_f(x)} {_f(shoulder)} "
        f"C {_f(x)} {_f(top + crown_h * 0.15)} {_f(x + w * 0.2)} {_f(top)} {_f(x + w / 2)} {_f(top)} "
        f"C {_f(x + w * 0.8)} {_f(top)} {_f(x + w)} {_f(top + crown_h * 0.15)} {_f(x + w)} {_f(shoulder)} "
        f"L {_f(x + w)} {_f(bottom)} Z"
    )
    parts: list[str] = [shape_path(outline)]
    # Textura del punto: columnas donde es elastico (el borde siempre; el
    # cuerpo y la corona si el gorro entero es elastico), V de jersey si no.
    body_sec = parts_by_id["body"]
    ribbed = bool(body_sec) and any(op.kind.value == "purl" for op in body_sec.steps[0].expanded_ops())
    gauge = resolve_gauge(pattern.params)
    column = max(6.0, 2 / gauge.stitches_per_cm * scale)  # una columna de 2 derechos
    rib_top = top if ribbed else bottom - brim_h
    texture: list[str] = [] if ribbed else knit_texture(x, top, w, h - brim_h, size=max(9.0, column))
    cx = x + column / 2
    while cx < x + w:
        texture.append(
            f'<line x1="{_f(cx)}" y1="{_f(rib_top)}" x2="{_f(cx)}" y2="{_f(bottom)}" '
            f'stroke="#c9ad91" stroke-width="{_f(column * 0.45)}" opacity="0.55"/>'
        )
        cx += 2 * column
    parts += clip_group("hat-outline", f'<path d="{outline}"/>', texture)
    parts.append(shape_path(outline, fill="none"))
    # Divisiones entre partes y sus nombres.
    y_brim = bottom - brim_h
    parts.append(dashed_line(x, y_brim, x + w, y_brim))
    parts.append(dashed_line(x, shoulder, x + w, shoulder))
    for sid, y0, y1 in (("brim", y_brim, bottom), ("body", shoulder, y_brim), ("crown", top, shoulder)):
        if lengths[sid] > 0:
            parts.append(label(x - 14, (y0 + y1) / 2 + 4, t(f"section.{sid}", lang), anchor="end", weight="700"))
            parts += dim_v(y0, y1, x + w + 22, (_fmt(pattern, lengths[sid]),), side="right", extension=-16)
    parts += dim_v(top, bottom, x + w + 110, (_mname(lang, "length"), _fmt(pattern, total)), side="right", extension=-100)
    parts += dim_h(x, x + w, bottom + 44, (_mname(lang, "width"), _fmt(pattern, flat)), extension=-40)
    parts.append(label(x + w / 2, bottom + 92, t("schematic.hat_flat_note", lang, circ=_fmt(pattern, circ)), color=TEXT_SOFT))
    return _frame(pattern, lang, parts)


def _cowl_svg(pattern: Pattern, lang: str) -> str:
    circ = _value(pattern, "circumference", 60.0)
    length = _value(pattern, "length", 30.0)
    return _rect_piece_svg(pattern, lang, piece_title="Cuello (tubo, plano)", width_cm=circ / 2, length_cm=length, w_key="width", l_key="length", cut="Tejer 1 en redondo")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_raglan_schematic_svg(pattern: Pattern, *, lang: str | None = None) -> str:
    return render_schematic_svg(pattern, lang=lang)


_SWEATERS = {
    "raglan_top_down", "yoke", "set_in", "set_in_sleeve", "drop_shoulder",
    "crochet_pullover", "crochet_cardigan", "cardigan", "vest", "crochet_vest",
}


def render_schematic_svg(
    pattern: Pattern, *, lang: str | None = None, letters_only: bool = False
) -> str:
    """Esquema SVG. `letters_only`: cotas solo con letras (PDF de varios talles,
    las medidas van en la tabla de talles)."""
    language = lang or pattern.params.idioma
    fam = pattern.meta.family
    try:
        keys = {m.key for m in pattern.measurements}
        if fam in _SWEATERS and ("sleeve_length" in keys or fam.endswith("vest")) and "bust" in keys:
            from render.sweater import render_sweater_svg

            return render_sweater_svg(pattern, language, values=not letters_only)
        if fam.startswith("home_"):
            from render.home import render_home_svg

            return render_home_svg(pattern, language)
        if fam in {"bag", "crochet_bag"}:
            return _bag_svg(pattern, language)
        if fam == "granny_square":
            from render.granny import render_granny_svg

            return render_granny_svg(pattern, language)
        if fam == "crochet_motif":
            from render.motif import render_motif_svg

            return render_motif_svg(pattern, language)
        if fam == "amigurumi" and any(s.meta.get("toy") for s in pattern.sections):
            from render.toy import render_toy_svg

            return render_toy_svg(pattern, language)
        from render.accessories import render_accessory_svg, supports

        if supports(fam):
            return render_accessory_svg(pattern, language)
        if fam == "hat":
            return _hat_svg(pattern, language)
        if fam == "cowl":
            return _cowl_svg(pattern, language)
        if fam in _PANEL_FAMILIES:
            return _panel_svg(pattern, language)
        if fam in {"raglan_top_down", "yoke", "drop_shoulder", "cardigan", "vest", "set_in_sleeve", "set_in", "flat"}:
            return _multi_piece_svg(pattern, language)
        # socks, mittens, amigurumi viejo -> panel-ish with their sections
        if fam in {"socks", "mittens", "amigurumi"}:
            return _multi_piece_svg(pattern, language)
        return _panel_svg(pattern, language)
    except Exception:
        # never fail pattern delivery because of drawing
        return _panel_svg(pattern, language)
