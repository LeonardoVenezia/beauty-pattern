"""Esquemas SVG por familia, dibujados con el kit tecnico de render.draw.

Cada familia tiene su silueta con cotas reales (flechas, lineas de extension)
y textura de tejido. Este mismo SVG se incrusta en el PDF via svglib: no hay
una segunda version del dibujo.
"""

from __future__ import annotations

import math

from engine.i18n import t
from engine.ir import Pattern
from render.draw import (
    FILL_ALT,
    STROKE,
    STROKE_FAINT,
    STROKE_SOFT,
    TEXT_SOFT,
    callout,
    caption,
    clip_group,
    crochet_texture,
    dashed_line,
    dim_h,
    dim_v,
    knit_texture,
    label,
    shape_path,
    shape_rect,
    svg_document,
    title_block,
)

WIDTH = 640.0
HEIGHT = 760.0
TOP = 118.0
BOTTOM = 690.0
_LEFT = 70.0
_RIGHT = WIDTH - 70.0

_PANEL_FAMILIES = {
    "scarf",
    "crochet_scarf",
    "shawl",
    "blanket",
    "flat_piece",
    "crochet_flat_piece",
}

# Compatibilidad: familias sin cuerpo de prenda con mangas.
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


def _measure(pattern: Pattern, key: str) -> float | None:
    for measurement in pattern.measurements:
        if measurement.key == key:
            return measurement.value_cm
    return None


def _value(pattern: Pattern, key: str) -> float:
    value = _measure(pattern, key)
    if value is None:
        raise KeyError(f"falta la medida {key!r}")
    return value


def _first_measure(
    pattern: Pattern, keys: tuple[str, ...]
) -> tuple[str, float] | None:
    for key in keys:
        value = _measure(pattern, key)
        if value is not None:
            return key, value
    return None


def _fmt(pattern: Pattern, value_cm: float) -> str:
    if pattern.params.unidades == "in":
        return f"{value_cm / 2.54:.1f} in"
    return f"{value_cm:.1f} cm"


def _mlabel(pattern: Pattern, key: str, lang: str) -> tuple[str, str]:
    """(nombre de la medida, valor con unidad) para calouts y cotas."""
    return t(f"measure.{key}", lang), _fmt(pattern, _value(pattern, key))


def _subtitle(pattern: Pattern, lang: str) -> str:
    garment_families = {
        "raglan_top_down",
        "drop_shoulder",
        "yoke",
        "set_in_sleeve",
        "cardigan",
        "vest",
    }
    unit = t("unit.cm" if pattern.params.unidades == "cm" else "unit.in", lang)
    if pattern.meta.family in garment_families:
        return t("schematic.size_measures_in", lang, size=pattern.meta.size, unit=unit)
    return t("schematic.measures_in", lang, unit=unit)


def _frame(
    pattern: Pattern,
    lang: str,
    parts: list[str],
) -> str:
    title = t(pattern.meta.title_key, lang)
    head = title_block(WIDTH, 44, title, _subtitle(pattern, lang))
    tail = [
        caption(WIDTH, HEIGHT - 36, t("schematic.caption", lang)),
    ]
    return svg_document(
        WIDTH,
        HEIGHT,
        title,
        t("pattern.schematic", lang),
        head + parts + tail,
    )


def _texture_for(pattern: Pattern, x: float, y: float, w: float, h: float) -> list[str]:
    if pattern.spec.tecnica.value == "crochet":
        return crochet_texture(x, y, w, h)
    return knit_texture(x, y, w, h)


# ---------------------------------------------------------------------------
# Pulpovers: raglan y canesu circular (vista frontal con mangas).
# ---------------------------------------------------------------------------


def _sweater_front(pattern: Pattern, lang: str, *, raglan: bool) -> str:
    bust = _value(pattern, "bust")
    body_length = _value(pattern, "body_length")
    sleeve_length = _value(pattern, "sleeve_length")
    upper_arm = _value(pattern, "upper_arm")
    neck = _value(pattern, "neck")
    yoke_depth = _value(pattern, "yoke_depth")
    wrist = _measure(pattern, "wrist")

    body_w_cm = bust / 2
    sleeve_w_cm = upper_arm / 2
    neck_w_cm = neck / 2
    total_w_cm = body_w_cm + 2 * sleeve_w_cm + 6.0
    total_h_cm = max(body_length, sleeve_length) + 2.0
    scale = min((_RIGHT - _LEFT) / total_w_cm, (BOTTOM - TOP) / total_h_cm)
    cx = WIDTH / 2
    top = TOP + 26.0
    underarm_y = top + yoke_depth * scale
    body_bottom = top + body_length * scale
    body_half = body_w_cm / 2 * scale
    neck_half = neck_w_cm / 2 * scale
    sleeve_px = sleeve_w_cm * scale
    neck_dip = min(16.0, neck_half * 0.5)

    # Silueta: escote con curva, hombros a la sisa, costados, ruedo.
    body_path = (
        f"M {_f(cx - neck_half)} {_f(top)} "
        f"Q {_f(cx - neck_half * 0.4)} {_f(top + neck_dip)} {_f(cx)} {_f(top + neck_dip)} "
        f"Q {_f(cx + neck_half * 0.4)} {_f(top + neck_dip)} {_f(cx + neck_half)} {_f(top)} "
        + (
            f"L {_f(cx + body_half)} {_f(underarm_y)} "
            if raglan
            else f"Q {_f(cx + body_half * 0.75)} {_f(top + (underarm_y - top) * 0.55)} "
            f"{_f(cx + body_half)} {_f(underarm_y)} "
        )
        + f"L {_f(cx + body_half)} {_f(body_bottom)} "
        f"L {_f(cx - body_half)} {_f(body_bottom)} "
        + (
            f"L {_f(cx - body_half)} {_f(underarm_y)} Z"
            if raglan
            else f"L {_f(cx - body_half)} {_f(underarm_y)} "
            f"Q {_f(cx - body_half * 0.75)} {_f(top + (underarm_y - top) * 0.55)} "
            f"{_f(cx - neck_half)} {_f(top)} Z"
        )
    )
    parts: list[str] = [shape_path(body_path)]
    parts += clip_group(
        f"body-{pattern.meta.id}",
        f'<path d="{body_path}"/>',
        _texture_for(pattern, cx - body_half, top, 2 * body_half, body_bottom - top),
    )

    sleeve_parts: list[str] = []
    cuff_bottoms: list[float] = []
    for side in (-1.0, 1.0):
        sx = cx + side * neck_half
        ux = cx + side * body_half
        if raglan:
            dx, dy = ux - sx, underarm_y - top
            seam_px = math.hypot(dx, dy)
            dirx, diry = dx / seam_px, dy / seam_px
            nx, ny = -side * diry, side * dirx
            s2x, s2y = sx + nx * sleeve_px, top + ny * sleeve_px
            u2x, u2y = ux + nx * sleeve_px, underarm_y + ny * sleeve_px
            extend_px = max(sleeve_length - seam_px / scale, 4.0) * scale
            c1x, c1y = ux + dirx * extend_px, underarm_y + diry * extend_px
            c2x, c2y = u2x + dirx * extend_px, u2y + diry * extend_px
            sleeve_d = (
                f"M {_f(sx)} {_f(top)} L {_f(ux)} {_f(underarm_y)} "
                f"L {_f(c1x)} {_f(c1y)} L {_f(c2x)} {_f(c2y)} "
                f"L {_f(s2x)} {_f(s2y)} Z"
            )
        else:
            rect_x = cx - body_half - sleeve_px if side < 0 else cx + body_half
            rect_w = sleeve_px
            cuff_y = underarm_y + (sleeve_length - yoke_depth) * scale
            sleeve_d = (
                f"M {_f(rect_x)} {_f(underarm_y)} L {_f(rect_x + rect_w)} {_f(underarm_y)} "
                f"L {_f(rect_x + rect_w)} {_f(cuff_y)} L {_f(rect_x)} {_f(cuff_y)} Z"
            )
            c1x, c1y = rect_x, cuff_y
            c2x, c2y = rect_x + rect_w, cuff_y
        sleeve_parts.append(shape_path(sleeve_d, fill=FILL_ALT))
        sleeve_parts += clip_group(
            f"sleeve-{pattern.meta.id}-{int(side)}",
            f'<path d="{sleeve_d}"/>',
            _texture_for(
                pattern,
                min(c1x, c2x) - 2.0,
                top,
                abs(c2x - c1x) + 4.0,
                max(c1y, c2y) - top + 4.0,
            ),
        )
        cuff_bottoms.append(max(c1y, c2y))

    parts = sleeve_parts + parts

    # Costuras de raglan sobre la silueta.
    if raglan:
        for side in (-1.0, 1.0):
            parts.append(
                f'<line x1="{_f(cx + side * neck_half)}" y1="{_f(top)}" '
                f'x2="{_f(cx + side * body_half)}" y2="{_f(underarm_y)}" '
                f'stroke="{STROKE}" stroke-width="1"/>'
            )
    else:
        parts.append(
            f'<line x1="{_f(cx - body_half)}" y1="{_f(underarm_y)}" '
            f'x2="{_f(cx + body_half)}" y2="{_f(underarm_y)}" '
            f'stroke="{STROKE_SOFT}" stroke-width="1" stroke-dasharray="6 4"/>'
        )

    # Cotas.
    neck_name, neck_value = _mlabel(pattern, "neck", lang)
    parts += dim_h(
        cx - neck_half,
        cx + neck_half,
        top - 34.0,
        (neck_name, neck_value),
        extension=30.0,
    )
    bust_name, bust_value = _mlabel(pattern, "bust", lang)
    parts += dim_h(
        cx - body_half,
        cx + body_half,
        body_bottom + 40.0,
        (bust_name, bust_value),
        extension=-(body_bottom - underarm_y + 30.0),
    )
    body_name, body_value = _mlabel(pattern, "body_length", lang)
    parts += dim_v(
        top,
        body_bottom,
        cx + body_half + 74.0,
        (body_name, body_value),
        side="right",
        extension=-(74.0 - 10.0),
    )
    yoke_name, yoke_value = _mlabel(pattern, "yoke_depth", lang)
    parts += dim_v(
        top,
        underarm_y,
        cx + body_half + 26.0,
        (yoke_name, yoke_value),
        side="right",
        extension=-16.0,
    )
    sleeve_name, sleeve_value = _mlabel(pattern, "sleeve_length", lang)
    left_sleeve_x = min(
        cx - body_half - sleeve_px,
        cx - neck_half - sleeve_px * 0.6,
    )
    parts += dim_v(
        top,
        max(cuff_bottoms),
        left_sleeve_x - 34.0,
        (sleeve_name, sleeve_value),
        side="left",
    )
    arm_name, arm_value = _mlabel(pattern, "upper_arm", lang)
    parts += callout(
        cx - body_half + sleeve_px * 0.4,
        top + (underarm_y - top) * 0.75,
        (arm_name, arm_value),
        dx=-30.0,
        dy=34.0,
        anchor="start",
    )
    if wrist is not None:
        wrist_name, wrist_value = _mlabel(pattern, "wrist", lang)
        parts += callout(
            cx - body_half - sleeve_px * 0.5,
            max(cuff_bottoms) - 18.0,
            (wrist_name, wrist_value),
            dx=-34.0,
            dy=26.0,
            anchor="start",
        )
    return _frame(pattern, lang, parts)


def _f(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Piezas planas: hombro caido, chaleco, cardigan, manga encajada.
# ---------------------------------------------------------------------------


def _panel_with_neck(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    neck_depth: float,
    neck_width: float,
    shoulder: float = 12.0,
) -> str:
    """Panel plano con curva de escote en el centro superior."""
    half = neck_width / 2
    d = (
        f"M {_f(x)} {_f(y)} L {_f(x + w)} {_f(y)} "
        f"L {_f(x + w)} {_f(y + h)} L {_f(x)} {_f(y + h)} Z "
        f"M {_f(x + w / 2 - half)} {_f(y)} "
        f"Q {_f(x + w / 2 - half * 0.2)} {_f(y + neck_depth)} {_f(x + w / 2)} {_f(y + neck_depth)} "
        f"Q {_f(x + w / 2 + half * 0.2)} {_f(y + neck_depth)} {_f(x + w / 2 + half)} {_f(y)}"
    )
    parts = [shape_rect(x, y, w, h)]
    # Escote: recorte visual (blanco sobre la curva).
    neck_d = (
        f"M {_f(x + w / 2 - half)} {_f(y - 2)} "
        f"L {_f(x + w / 2 - half)} {_f(y)} "
        f"Q {_f(x + w / 2 - half * 0.2)} {_f(y + neck_depth)} {_f(x + w / 2)} {_f(y + neck_depth)} "
        f"Q {_f(x + w / 2 + half * 0.2)} {_f(y + neck_depth)} {_f(x + w / 2 + half)} {_f(y)} "
        f"L {_f(x + w / 2 + half)} {_f(y - 2)} Z"
    )
    parts.append(f'<path d="{neck_d}" fill="#ffffff" stroke="{STROKE}" stroke-width="2"/>')
    del d, shoulder
    return "".join(parts)


def _flat_pieces_svg(pattern: Pattern, lang: str) -> str:
    bust = _value(pattern, "bust")
    body_length = _value(pattern, "body_length")
    sleeve_length = _measure(pattern, "sleeve_length")
    upper_arm = _measure(pattern, "upper_arm")
    neck = _value(pattern, "neck")

    family = pattern.meta.family
    is_cardigan = family == "cardigan"
    back_w_cm = bust / 2
    front_w_cm = bust / 4 if is_cardigan else bust / 2
    neck_cm = neck / 2

    columns = 3 if is_cardigan else 2
    if sleeve_length is not None:
        columns += 1
    gap = 46.0
    total_cm = back_w_cm + front_w_cm * (2 if is_cardigan else 1)
    if sleeve_length is not None and upper_arm is not None:
        total_cm += upper_arm / 2
    scale = min(
        (_RIGHT - _LEFT - gap * (columns - 1)) / total_cm,
        (BOTTOM - TOP) / (body_length + 8.0),
    )
    panel_h = body_length * scale
    back_w = back_w_cm * scale
    front_w = front_w_cm * scale
    neck_w = neck_cm * scale

    y = TOP + 16.0
    x = _LEFT
    parts: list[str] = []

    back = _panel_with_neck(x, y, back_w, panel_h, neck_depth=14.0, neck_width=neck_w * 0.8)
    parts.append(back)
    parts += clip_group(
        f"back-{pattern.meta.id}",
        f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(back_w)}" height="{_f(panel_h)}"/>',
        _texture_for(pattern, x, y + 18.0, back_w, panel_h - 18.0),
    )
    parts.append(label(x + back_w / 2, y - 12.0, t("section.back", lang), size=11, color=TEXT_SOFT))
    x += back_w + gap

    if is_cardigan:
        for _ in range(2):
            front = _panel_with_neck(
                x, y, front_w, panel_h, neck_depth=22.0, neck_width=neck_w * 0.7
            )
            parts.append(front)
            parts += clip_group(
                f"front-{pattern.meta.id}-{int(x)}",
                f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(front_w)}" height="{_f(panel_h)}"/>',
                _texture_for(pattern, x, y + 24.0, front_w, panel_h - 24.0),
            )
            parts.append(
                label(x + front_w / 2, y - 12.0, t("section.front", lang), size=11, color=TEXT_SOFT)
            )
            # Banda de botones en el borde interior del primer delantero.
            parts.append(dashed_line(x, y, x, y + panel_h))
            x += front_w + gap
    else:
        front = _panel_with_neck(
            x, y, front_w, panel_h, neck_depth=26.0, neck_width=neck_w
        )
        parts.append(front)
        parts += clip_group(
            f"front-{pattern.meta.id}",
            f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(front_w)}" height="{_f(panel_h)}"/>',
            _texture_for(pattern, x, y + 28.0, front_w, panel_h - 28.0),
        )
        parts.append(
            label(x + front_w / 2, y - 12.0, t("section.front", lang), size=11, color=TEXT_SOFT)
        )
        x += front_w + gap

    sleeve_w = 0.0
    if sleeve_length is not None and upper_arm is not None:
        sleeve_w = upper_arm / 2 * scale
        sleeve_h = sleeve_length * scale
        parts.append(shape_rect(x, y, sleeve_w, sleeve_h, fill=FILL_ALT))
        parts += clip_group(
            f"sleeve-{pattern.meta.id}",
            f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(sleeve_w)}" height="{_f(sleeve_h)}"/>',
            _texture_for(pattern, x, y, sleeve_w, sleeve_h),
        )
        parts.append(
            label(x + sleeve_w / 2, y - 12.0, t("section.sleeve", lang), size=11, color=TEXT_SOFT)
        )

    # Cotas: ancho de espalda, largo del cuerpo, manga.
    _bust_name, _bust_value = _mlabel(pattern, "bust", lang)
    back_x = _LEFT
    parts += dim_h(
        back_x,
        back_x + back_w,
        y + panel_h + 44.0,
        (t("schematic.back_width", lang), f"{_fmt(pattern, bust / 2)}"),
        extension=-(panel_h + 36.0),
    )
    body_name, body_value = _mlabel(pattern, "body_length", lang)
    parts += dim_v(
        y,
        y + panel_h,
        x - 26.0 if sleeve_w else _RIGHT - 14.0,
        (body_name, body_value),
        side="left" if sleeve_w else "right",
        extension=0.0,
    )
    if sleeve_length is not None and upper_arm is not None:
        sleeve_name, sleeve_value = _mlabel(pattern, "sleeve_length", lang)
        parts += dim_v(
            y,
            y + sleeve_h,
            x + sleeve_w + 26.0,
            (sleeve_name, sleeve_value),
            side="right",
        )
        arm_name, arm_value = _mlabel(pattern, "upper_arm", lang)
        parts += callout(
            x + sleeve_w / 2,
            y + sleeve_h * 0.55,
            (arm_name, arm_value),
            dx=-34.0,
            dy=30.0,
        )
    return _frame(pattern, lang, parts)


def _set_in_svg(pattern: Pattern, lang: str) -> str:
    bust = _value(pattern, "bust")
    body_length = _value(pattern, "body_length")
    sleeve_length = _value(pattern, "sleeve_length")
    upper_arm = _value(pattern, "upper_arm")
    armhole = _measure(pattern, "armhole")

    body_w_cm = bust / 2
    sleeve_w_cm = upper_arm / 2
    gap = 56.0
    total_cm = body_w_cm + sleeve_w_cm
    scale = min(
        (_RIGHT - _LEFT - gap) / total_cm,
        (BOTTOM - TOP) / (max(body_length, sleeve_length) + 8.0),
    )
    body_w = body_w_cm * scale
    body_h = body_length * scale
    sleeve_w = sleeve_w_cm * scale
    sleeve_h = sleeve_length * scale
    y = TOP + 24.0
    x_body = _LEFT
    x_sleeve = x_body + body_w + gap

    # Cuerpo: sisa en los bordes superiores y escote al centro.
    armhole_px = armhole * scale if armhole else body_h * 0.22
    shoulder = 26.0
    body_d = (
        f"M {_f(x_body)} {_f(y + armhole_px)} "
        f"Q {_f(x_body)} {_f(y)} {_f(x_body + shoulder)} {_f(y)} "
        f"L {_f(x_body + body_w / 2 - 34)} {_f(y)} "
        f"Q {_f(x_body + body_w / 2)} {_f(y + 30)} {_f(x_body + body_w / 2 + 34)} {_f(y)} "
        f"L {_f(x_body + body_w - shoulder)} {_f(y)} "
        f"Q {_f(x_body + body_w)} {_f(y)} {_f(x_body + body_w)} {_f(y + armhole_px)} "
        f"L {_f(x_body + body_w)} {_f(y + body_h)} "
        f"L {_f(x_body)} {_f(y + body_h)} Z"
    )
    parts: list[str] = [shape_path(body_d)]
    parts += clip_group(
        f"body-{pattern.meta.id}",
        f'<path d="{body_d}"/>',
        _texture_for(pattern, x_body, y, body_w, body_h),
    )

    # Manga: copa curva arriba, cuerpo parejo, puno abajo.
    cap_h = armhole_px * 0.8
    sleeve_d = (
        f"M {_f(x_sleeve + sleeve_w * 0.18)} {_f(y)} "
        f"Q {_f(x_sleeve)} {_f(y + cap_h)} {_f(x_sleeve + sleeve_w * 0.14)} {_f(y + cap_h * 1.6)} "
        f"L {_f(x_sleeve + sleeve_w * 0.14)} {_f(y + sleeve_h)} "
        f"L {_f(x_sleeve + sleeve_w * 0.86)} {_f(y + sleeve_h)} "
        f"L {_f(x_sleeve + sleeve_w * 0.86)} {_f(y + cap_h * 1.6)} "
        f"Q {_f(x_sleeve + sleeve_w)} {_f(y + cap_h)} {_f(x_sleeve + sleeve_w * 0.82)} {_f(y)} Z"
    )
    parts.append(shape_path(sleeve_d, fill=FILL_ALT))
    parts += clip_group(
        f"sleeve-{pattern.meta.id}",
        f'<path d="{sleeve_d}"/>',
        _texture_for(pattern, x_sleeve, y, sleeve_w, sleeve_h),
    )

    _bust_name, _bust_value = _mlabel(pattern, "bust", lang)
    parts += dim_h(
        x_body,
        x_body + body_w,
        y + body_h + 44.0,
        (t("schematic.back_width", lang), _fmt(pattern, bust / 2)),
        extension=-(body_h + 36.0),
    )
    body_name, body_value = _mlabel(pattern, "body_length", lang)
    parts += dim_v(
        y,
        y + body_h,
        x_body - 26.0,
        (body_name, body_value),
        side="left",
    )
    sleeve_name, sleeve_value = _mlabel(pattern, "sleeve_length", lang)
    parts += dim_v(
        y,
        y + sleeve_h,
        x_sleeve + sleeve_w + 26.0,
        (sleeve_name, sleeve_value),
        side="right",
    )
    arm_name, arm_value = _mlabel(pattern, "upper_arm", lang)
    parts += callout(
        x_sleeve + sleeve_w / 2,
        y + sleeve_h * 0.6,
        (arm_name, arm_value),
        dx=36.0,
        dy=26.0,
    )
    if armhole is not None:
        parts += callout(
            x_body + body_w,
            y + armhole_px * 0.55,
            (t("measure.armhole", lang), _fmt(pattern, armhole)),
            dx=22.0,
            dy=-30.0,
        )
    return _frame(pattern, lang, parts)


# ---------------------------------------------------------------------------
# Accesorios y crochet.
# ---------------------------------------------------------------------------


def _hat_svg(pattern: Pattern, lang: str) -> str:
    head = _value(pattern, "head")
    length = _value(pattern, "length")
    flat_w_cm = head / 2
    scale = min((_RIGHT - _LEFT - 80.0) / flat_w_cm, (BOTTOM - TOP) / length)
    w = flat_w_cm * scale
    h = length * scale
    cx = WIDTH / 2
    x = cx - w / 2
    y = TOP + 18.0
    brim_h = h * 0.16
    brim_w = w * 1.06
    dome_h = h * 0.42

    body_d = (
        f"M {_f(x)} {_f(y + h - brim_h)} "
        f"L {_f(x)} {_f(y + dome_h)} "
        f"Q {_f(x)} {_f(y)} {_f(cx)} {_f(y)} "
        f"Q {_f(x + w)} {_f(y)} {_f(x + w)} {_f(y + dome_h)} "
        f"L {_f(x + w)} {_f(y + h - brim_h)} Z"
    )
    parts: list[str] = [shape_path(body_d)]
    parts += clip_group(
        f"hat-{pattern.meta.id}",
        f'<path d="{body_d}"/>',
        _texture_for(pattern, x, y, w, h - brim_h),
    )
    parts.append(
        shape_rect(
            x - (brim_w - w) / 2,
            y + h - brim_h,
            brim_w,
            brim_h,
            rx=6.0,
            fill=FILL_ALT,
            width=2,
        )
    )
    for i in range(1, 4):
        t_ = i / 4
        parts.append(
            dashed_line(
                cx + (x - cx) * (1 - t_ * 0.25),
                y + dome_h * t_,
                cx + (x + w - cx) * (1 - t_ * 0.25),
                y + dome_h * t_,
                color=STROKE_FAINT,
            )
        )

    length_name, length_value = _mlabel(pattern, "length", lang)
    parts += dim_v(
        y,
        y + h,
        x + w + 46.0,
        (length_name, length_value),
        side="right",
        extension=-36.0,
    )
    head_name, head_value = _mlabel(pattern, "head", lang)
    parts += callout(
        cx - w * 0.35,
        y + h - brim_h / 2,
        (head_name, head_value),
        dx=-40.0,
        dy=-38.0,
    )
    return _frame(pattern, lang, parts)


def _cowl_svg(pattern: Pattern, lang: str) -> str:
    circumference = _value(pattern, "circumference")
    length = _value(pattern, "length")
    flat_w_cm = circumference / 2
    scale = min((_RIGHT - _LEFT - 120.0) / flat_w_cm, (BOTTOM - TOP) / length)
    w = flat_w_cm * scale
    h = length * scale
    cx = WIDTH / 2
    x = cx - w / 2
    y = TOP + 30.0
    ellipse_ry = w * 0.14

    tube_d = (
        f"M {_f(x)} {_f(y)} "
        f"L {_f(x)} {_f(y + h)} "
        f"A {_f(w / 2)} {_f(ellipse_ry)} 0 0 0 {_f(x + w)} {_f(y + h)} "
        f"L {_f(x + w)} {_f(y)} "
        f"A {_f(w / 2)} {_f(ellipse_ry)} 0 0 1 {_f(x)} {_f(y)} Z"
    )
    parts: list[str] = [shape_path(tube_d)]
    parts += clip_group(
        f"cowl-{pattern.meta.id}",
        f'<path d="{tube_d}"/>',
        _texture_for(pattern, x, y + ellipse_ry, w, h - ellipse_ry),
    )
    parts.append(
        f'<ellipse cx="{_f(cx)}" cy="{_f(y)}" rx="{_f(w / 2)}" ry="{_f(ellipse_ry)}" '
        f'fill="{FILL_ALT}" stroke="{STROKE}" stroke-width="2"/>'
    )
    length_name, length_value = _mlabel(pattern, "length", lang)
    parts += dim_v(
        y,
        y + h,
        x + w + 46.0,
        (length_name, length_value),
        side="right",
        extension=-36.0,
    )
    circ_name, circ_value = _mlabel(pattern, "circumference", lang)
    parts += callout(
        cx,
        y,
        (circ_name, circ_value),
        dx=54.0,
        dy=-30.0,
    )
    return _frame(pattern, lang, parts)


def _socks_svg(pattern: Pattern, lang: str) -> str:
    circumference = _value(pattern, "circumference")
    foot_length = _value(pattern, "foot_length")
    toe_length = _measure(pattern, "toe_length")
    leg_cm = 22.0
    total_h_cm = leg_cm + foot_length
    leg_w_cm = circumference / 2
    foot_w_cm = leg_w_cm * 0.8
    scale = min(
        (_RIGHT - _LEFT - 60.0) / (leg_w_cm + foot_length * 0.6),
        (BOTTOM - TOP) / total_h_cm,
    )
    leg_w = leg_w_cm * scale
    foot_w = foot_w_cm * scale
    h_leg = leg_cm * scale
    h_foot = foot_length * scale
    x = WIDTH / 2 - (leg_w + foot_length * scale) / 2 + 10.0
    y = TOP + 26.0
    ankle_y = y + h_leg * 0.62

    sock_d = (
        f"M {_f(x)} {_f(y)} L {_f(x + leg_w)} {_f(y)} "
        f"L {_f(x + leg_w)} {_f(ankle_y)} "
        f"L {_f(x + leg_w * 0.55 + foot_w)} {_f(ankle_y)} "
        f"Q {_f(x + leg_w * 0.55 + foot_w + 26)} {_f(ankle_y + h_foot * 0.55)} "
        f"{_f(x + leg_w * 0.55 + foot_w * 0.6)} {_f(y + h_leg + h_foot)} "
        f"L {_f(x + leg_w * 0.55)} {_f(y + h_leg + h_foot)} "
        f"L {_f(x)} {_f(y + h_leg)} Z"
    )
    parts: list[str] = [shape_path(sock_d)]
    parts += clip_group(
        f"sock-{pattern.meta.id}",
        f'<path d="{sock_d}"/>',
        _texture_for(pattern, x, y, leg_w + 30.0, h_leg + h_foot),
    )
    parts.append(
        f'<rect x="{_f(x - 3)}" y="{_f(y)}" width="{_f(leg_w + 6)}" height="{_f(h_leg * 0.14)}" '
        f'rx="5" fill="{FILL_ALT}" stroke="{STROKE}" stroke-width="2"/>'
    )

    foot_name, foot_value = _mlabel(pattern, "foot_length", lang)
    parts += dim_h(
        x + leg_w * 0.55,
        x + leg_w * 0.55 + foot_w * 0.6 + 26.0,
        y + h_leg + h_foot + 44.0,
        (foot_name, foot_value),
        extension=-(h_leg + h_foot + 36.0),
    )
    circ_name, circ_value = _mlabel(pattern, "circumference", lang)
    parts += callout(
        x + leg_w * 0.5,
        y + h_leg * 0.3,
        (circ_name, circ_value),
        dx=-44.0,
        dy=-26.0,
    )
    if toe_length is not None:
        parts += callout(
            x + leg_w * 0.55 + foot_w * 0.75,
            ankle_y + h_foot * 0.55,
            (t("measure.toe_length", lang), _fmt(pattern, toe_length)),
            dx=30.0,
            dy=-34.0,
        )
    return _frame(pattern, lang, parts)


def _mittens_svg(pattern: Pattern, lang: str) -> str:
    palm = _value(pattern, "palm")
    length = _value(pattern, "length")
    thumb = _measure(pattern, "thumb") or 6.0
    flat_w_cm = palm / 2
    scale = min((_RIGHT - _LEFT - 110.0) / (flat_w_cm * 1.4), (BOTTOM - TOP) / length)
    hand_w = flat_w_cm * scale
    hand_h = length * scale
    x = WIDTH / 2 - hand_w * 0.7
    y = TOP + 26.0
    thumb_w = max(20.0, hand_w * 0.26)
    thumb_h = max(26.0, thumb * scale)
    thumb_x = x + hand_w - thumb_w * 0.5
    thumb_y = y + hand_h * 0.55

    hand_d = (
        f"M {_f(x)} {_f(y + hand_h * 0.42)} "
        f"Q {_f(x)} {_f(y)} {_f(x + hand_w * 0.32)} {_f(y)} "
        f"L {_f(x + hand_w * 0.68)} {_f(y)} "
        f"Q {_f(x + hand_w)} {_f(y)} {_f(x + hand_w)} {_f(y + hand_h * 0.42)} "
        f"L {_f(x + hand_w)} {_f(y + hand_h * 0.86)} "
        f"Q {_f(x + hand_w)} {_f(y + hand_h)} {_f(x + hand_w * 0.85)} {_f(y + hand_h)} "
        f"L {_f(x + hand_w * 0.15)} {_f(y + hand_h)} "
        f"Q {_f(x)} {_f(y + hand_h)} {_f(x)} {_f(y + hand_h * 0.86)} Z"
    )
    thumb_d = (
        f"M {_f(thumb_x)} {_f(thumb_y + thumb_h * 0.6)} "
        f"L {_f(thumb_x)} {_f(y + hand_h * 0.78)} "
        f"Q {_f(thumb_x)} {_f(y + hand_h * 0.88)} {_f(thumb_x + thumb_w * 0.7)} "
        f"{_f(y + hand_h * 0.9)} "
        f"Q {_f(thumb_x + thumb_w)} {_f(y + hand_h * 0.86)} {_f(thumb_x + thumb_w)} "
        f"{_f(y + hand_h * 0.66)} "
        f"L {_f(thumb_x + thumb_w)} {_f(thumb_y)} "
        f"Q {_f(thumb_x + thumb_w)} {_f(thumb_y - thumb_h * 0.3)} {_f(thumb_x + thumb_w * 0.5)} "
        f"{_f(thumb_y - thumb_h * 0.3)} "
        f"Q {_f(thumb_x)} {_f(thumb_y - thumb_h * 0.3)} {_f(thumb_x)} {_f(thumb_y)} "
        f"L {_f(thumb_x)} {_f(thumb_y + thumb_h * 0.6)} Z"
    )
    parts: list[str] = [shape_path(hand_d), shape_path(thumb_d, fill=FILL_ALT)]
    parts += clip_group(
        f"mitten-{pattern.meta.id}",
        f'<path d="{hand_d}"/>',
        _texture_for(pattern, x, y, hand_w, hand_h),
    )
    parts.append(dashed_line(x, y + hand_h * 0.88, x + hand_w, y + hand_h * 0.88))

    length_name, length_value = _mlabel(pattern, "length", lang)
    parts += dim_v(
        y,
        y + hand_h,
        x - 34.0,
        (length_name, length_value),
        side="left",
    )
    palm_name, palm_value = _mlabel(pattern, "palm", lang)
    parts += callout(
        x + hand_w * 0.4,
        y + hand_h * 0.3,
        (palm_name, palm_value),
        dx=hand_w * 0.2 + 40.0,
        dy=-30.0,
    )
    thumb_name, thumb_value = _mlabel(pattern, "thumb", lang)
    parts += dim_v(
        y + hand_h * 0.66,
        y + hand_h * 0.9,
        thumb_x + thumb_w + 30.0,
        (thumb_name, thumb_value),
        side="right",
    )
    return _frame(pattern, lang, parts)


def _panel_svg(pattern: Pattern, lang: str) -> str:
    width_measure = _first_measure(pattern, ("width", "diameter", "circumference", "size"))
    length_measure = _first_measure(pattern, ("length", "height", "foot_length"))
    if width_measure is None or length_measure is None:
        raise KeyError("la pieza no tiene medidas de ancho y largo")
    width_key, width_cm = width_measure
    length_key, length_cm = length_measure
    scale = min((_RIGHT - _LEFT) / width_cm, (BOTTOM - TOP - 40.0) / length_cm)
    w = width_cm * scale
    h = length_cm * scale
    x = (WIDTH - w) / 2
    y = TOP + 22.0

    parts: list[str] = [shape_rect(x, y, w, h, rx=4.0)]
    parts += clip_group(
        f"panel-{pattern.meta.id}",
        f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" rx="4"/>',
        _texture_for(pattern, x + 6.0, y + 6.0, w - 12.0, h - 12.0),
    )
    if pattern.meta.family in {"scarf", "crochet_scarf"}:
        for fringe_x in (x, x + w):
            for i in range(4):
                fy = y + h * (0.25 + i * 0.17)
                parts.append(
                    f'<line x1="{_f(fringe_x)}" y1="{_f(fy)}" '
                    f'x2="{_f(fringe_x + (-14 if fringe_x == x else 14))}" '
                    f'y2="{_f(fy + 10)}" stroke="{STROKE_SOFT}" stroke-width="1.4"/>'
                )
    width_name, width_value = _mlabel(pattern, width_key, lang)
    parts += dim_h(
        x,
        x + w,
        y + h + 46.0,
        (width_name, width_value),
        extension=-(h + 38.0),
    )
    length_name, length_value = _mlabel(pattern, length_key, lang)
    parts += dim_v(
        y,
        y + h,
        x + w + 40.0,
        (length_name, length_value),
        side="right",
        extension=-30.0,
    )
    return _frame(pattern, lang, parts)


def _bag_svg(pattern: Pattern, lang: str) -> str:
    width_cm = _value(pattern, "width")
    length_cm = _value(pattern, "length")
    scale = min(360.0 / width_cm, 300.0 / length_cm)
    w = width_cm * scale
    h = length_cm * scale
    x = (WIDTH - w) / 2
    y = TOP + 74.0
    bottom = y + h
    radius = 14.0
    handle_top = y - 64.0

    body_d = (
        f"M {_f(x)} {_f(y)} L {_f(x + w)} {_f(y)} "
        f"L {_f(x + w)} {_f(bottom - radius)} "
        f"Q {_f(x + w)} {_f(bottom)} {_f(x + w - radius)} {_f(bottom)} "
        f"L {_f(x + radius)} {_f(bottom)} "
        f"Q {_f(x)} {_f(bottom)} {_f(x)} {_f(bottom - radius)} Z"
    )
    parts: list[str] = []
    for index, color in ((0, "#cbb49f"), (1, STROKE_SOFT)):
        hx1 = x + w * 0.24 + index * 8.0
        hx2 = x + w * 0.76 - index * 8.0
        hy = handle_top + index * 12.0
        parts.append(
            f'<path d="M {_f(hx1)} {_f(y - 6)} L {_f(hx1)} {_f(hy + 20)} '
            f'Q {_f(hx1)} {_f(hy)} {_f(hx1 + 16)} {_f(hy)} '
            f'L {_f(hx2 - 16)} {_f(hy)} Q {_f(hx2)} {_f(hy)} {_f(hx2)} {_f(hy + 20)} '
            f'L {_f(hx2)} {_f(y - 6)}" fill="none" stroke="{color}" '
            f'stroke-width="8" stroke-linecap="round" stroke-dasharray="10 6"/>'
        )
    parts.append(shape_path(body_d))
    parts += clip_group(
        f"bag-{pattern.meta.id}",
        f'<path d="{body_d}"/>',
        _texture_for(pattern, x + 12.0, y + 26.0, w - 24.0, h - 40.0),
    )
    parts.append(dashed_line(x + 10.0, y + 18.0, x + w - 10.0, y + 18.0))
    parts.append(label(x + 16.0, y + 12.0, t("schematic.fold", lang), size=9, anchor="start", color=TEXT_SOFT))
    parts.append(
        label(WIDTH / 2, handle_top - 12.0, t("schematic.optional_handles", lang), size=10, color=TEXT_SOFT)
    )
    width_name, width_value = _mlabel(pattern, "width", lang)
    parts += dim_h(
        x,
        x + w,
        bottom + 46.0,
        (width_name, width_value),
        extension=-(h + 38.0),
    )
    length_name, length_value = _mlabel(pattern, "length", lang)
    parts += dim_v(
        y,
        bottom,
        x + w + 40.0,
        (length_name, length_value),
        side="right",
        extension=-30.0,
    )
    return _frame(pattern, lang, parts)


def _granny_svg(pattern: Pattern, lang: str) -> str:
    side_measure = _first_measure(pattern, ("width", "size"))
    if side_measure is None:
        raise KeyError("el granny square no declara su lado")
    side_key, side_cm = side_measure
    length_measure = _first_measure(pattern, ("length",))
    if length_measure is not None:
        side_cm = min(side_cm, length_measure[1])
    scale = min(380.0 / side_cm, 380.0 / side_cm)
    side = side_cm * scale
    x = (WIDTH - side) / 2
    y = TOP + 60.0

    parts: list[str] = [shape_rect(x, y, side, side, rx=6.0)]
    parts += clip_group(
        f"granny-{pattern.meta.id}",
        f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(side)}" height="{_f(side)}" rx="6"/>',
        crochet_texture(x + 14.0, y + 14.0, side - 28.0, side - 28.0, size=16.0),
    )
    for inset in (0.14, 0.26, 0.38):
        ix = x + side * inset
        iy = y + side * inset
        iw = side * (1 - 2 * inset)
        parts.append(
            f'<rect x="{_f(ix)}" y="{_f(iy)}" width="{_f(iw)}" height="{_f(iw)}" '
            f'fill="none" stroke="{STROKE_SOFT}" stroke-width="1" stroke-dasharray="6 4"/>'
        )
    for corner_x in (x + 12.0, x + side - 12.0):
        for corner_y in (y + 12.0, y + side - 12.0):
            parts.append(
                f'<circle cx="{_f(corner_x)}" cy="{_f(corner_y)}" r="3.4" fill="{STROKE_SOFT}"/>'
            )
    parts.append(
        label(WIDTH / 2, y - 16.0, t("schematic.granny_base", lang), size=10, color=TEXT_SOFT)
    )
    side_name, side_value = _mlabel(pattern, side_key, lang)
    parts += dim_h(
        x,
        x + side,
        y + side + 46.0,
        (side_name, side_value),
        extension=-(side + 38.0),
    )
    parts += dim_v(
        y,
        y + side,
        x + side + 40.0,
        (side_name, side_value),
        side="right",
        extension=-30.0,
    )
    return _frame(pattern, lang, parts)


def _amigurumi_svg(pattern: Pattern, lang: str) -> str:
    diameter = _value(pattern, "diameter")
    height = _value(pattern, "height")
    form = pattern.spec.forma or "straight"
    scale = min(320.0 / diameter, 380.0 / height)
    w = diameter * scale
    h = height * scale
    cx = WIDTH / 2
    y = TOP + 50.0
    bottom = y + h

    if form == "boxy":
        body_d = (
            f"M {_f(cx - w / 2)} {_f(y)} L {_f(cx + w / 2)} {_f(y)} "
            f"L {_f(cx + w / 2)} {_f(bottom - w * 0.2)} "
            f"Q {_f(cx + w / 2)} {_f(bottom)} {_f(cx + w / 2 - w * 0.2)} {_f(bottom)} "
            f"L {_f(cx - w / 2 + w * 0.2)} {_f(bottom)} "
            f"Q {_f(cx - w / 2)} {_f(bottom)} {_f(cx - w / 2)} {_f(bottom - w * 0.2)} Z"
        )
    elif form in {"a_line", "curved"}:
        top_w = w * 0.42
        body_d = (
            f"M {_f(cx - top_w / 2)} {_f(y)} "
            f"Q {_f(cx + top_w / 2)} {_f(y)} {_f(cx + w * 0.34)} {_f(y + h * 0.5)} "
            f"Q {_f(cx + w / 2)} {_f(bottom - h * 0.12)} {_f(cx + w / 2 - w * 0.08)} {_f(bottom)} "
            f"L {_f(cx - w / 2 + w * 0.08)} {_f(bottom)} "
            f"Q {_f(cx - w / 2)} {_f(bottom - h * 0.12)} {_f(cx - w * 0.34)} {_f(y + h * 0.5)} "
            f"Q {_f(cx - top_w / 2)} {_f(y)} {_f(cx - top_w / 2)} {_f(y)} Z"
        )
    else:
        body_d = (
            f"M {_f(cx - w / 2)} {_f(y + h / 2)} "
            f"A {_f(w / 2)} {_f(h / 2)} 0 1 0 {_f(cx + w / 2)} {_f(y + h / 2)} "
            f"A {_f(w / 2)} {_f(h / 2)} 0 1 0 {_f(cx - w / 2)} {_f(y + h / 2)} Z"
        )
    parts: list[str] = [shape_path(body_d)]
    parts += clip_group(
        f"amigurumi-{pattern.meta.id}",
        f'<path d="{body_d}"/>',
        crochet_texture(cx - w / 2, y, w, h, size=13.0),
    )
    diameter_name, diameter_value = _mlabel(pattern, "diameter", lang)
    parts += dim_h(
        cx - w / 2,
        cx + w / 2,
        bottom + 46.0,
        (diameter_name, diameter_value),
        extension=-(h * 0.5 + 38.0) if form != "straight" else -(h + 38.0),
    )
    height_name, height_value = _mlabel(pattern, "height", lang)
    parts += dim_v(
        y,
        bottom,
        cx + w / 2 + 40.0,
        (height_name, height_value),
        side="right",
        extension=-30.0,
    )
    return _frame(pattern, lang, parts)


# ---------------------------------------------------------------------------
# Despacho publico.
# ---------------------------------------------------------------------------


def render_raglan_schematic_svg(
    pattern: Pattern, *, lang: str | None = None
) -> str:
    language = lang or pattern.params.idioma
    return _sweater_front(pattern, language, raglan=True)


def render_schematic_svg(pattern: Pattern, *, lang: str | None = None) -> str:
    language = lang or pattern.params.idioma
    family = pattern.meta.family
    if family == "raglan_top_down":
        return _sweater_front(pattern, language, raglan=True)
    if family == "yoke":
        return _sweater_front(pattern, language, raglan=False)
    if family in {"drop_shoulder", "cardigan", "vest"}:
        return _flat_pieces_svg(pattern, language)
    if family in {"set_in_sleeve", "set_in"}:
        return _set_in_svg(pattern, language)
    if family == "hat":
        return _hat_svg(pattern, language)
    if family == "cowl":
        return _cowl_svg(pattern, language)
    if family == "socks":
        return _socks_svg(pattern, language)
    if family == "mittens":
        return _mittens_svg(pattern, language)
    if family in {"bag", "crochet_bag"}:
        return _bag_svg(pattern, language)
    if family == "granny_square":
        return _granny_svg(pattern, language)
    if family == "amigurumi":
        return _amigurumi_svg(pattern, language)
    if family in _PANEL_FAMILIES:
        return _panel_svg(pattern, language)
    return _panel_svg(pattern, language)
