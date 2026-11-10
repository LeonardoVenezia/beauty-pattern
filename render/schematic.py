"""Esquema SVG de medidas para el pullover raglan."""

from __future__ import annotations

from xml.sax.saxutils import escape

from engine.i18n import t
from engine.ir import Pattern


def _value(pattern: Pattern, key: str) -> float:
    for measurement in pattern.measurements:
        if measurement.key == key:
            return measurement.value_cm
    raise KeyError(f"falta la medida {key!r}")


def _label(pattern: Pattern, key: str, lang: str) -> str:
    return t(f"measure.{key}", lang)


def _fmt(pattern: Pattern, value_cm: float) -> str:
    if pattern.params.unidades == "in":
        return f"{value_cm / 2.54:.1f} in"
    return f"{value_cm:.1f} cm"


def render_raglan_schematic_svg(
    pattern: Pattern, *, lang: str | None = None
) -> str:
    language = lang or pattern.params.idioma
    bust = _value(pattern, "bust")
    body_length = _value(pattern, "body_length")
    sleeve_length = _value(pattern, "sleeve_length")
    upper_arm = _value(pattern, "upper_arm")
    neck = _value(pattern, "neck")
    yoke_depth = _value(pattern, "yoke_depth")

    body_w = bust / 2
    sleeve_w = upper_arm / 2
    total_w = body_w + 2 * sleeve_w
    max_h = max(body_length, sleeve_length)
    width, height = 640.0, 820.0
    margin, label_h = 40.0, 100.0
    scale = min(
        (width - 2 * margin) / total_w,
        (height - 2 * margin - label_h) / max_h,
    )
    cx = width / 2
    top = margin + 30
    body_top = top + yoke_depth * scale
    body_bottom = body_top + (body_length - yoke_depth) * scale
    body_x = cx - body_w * scale / 2
    sleeve_top = body_top
    sleeve_bottom = sleeve_top + (sleeve_length - yoke_depth) * scale
    sleeve_left_x = body_x - sleeve_w * scale
    sleeve_right_x = body_x + body_w * scale
    neck_half = neck / 2 * scale
    body_half = body_w / 2 * scale

    title = t(pattern.meta.title_key, language)
    desc = t("pattern.schematic", language)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img" '
        'aria-labelledby="schematic-title schematic-desc">',
        f'<title id="schematic-title">{escape(title)}</title>',
        f'<desc id="schematic-desc">{escape(desc)}</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<g stroke="#6b4f3a" stroke-width="1.5" fill="#f2e8dc">',
        f'<polygon points="{cx - neck_half:.1f},{top:.1f} '
        f'{cx + neck_half:.1f},{top:.1f} '
        f'{cx + body_half:.1f},{body_top:.1f} '
        f'{cx - body_half:.1f},{body_top:.1f}"/>',
        f'<rect x="{body_x:.1f}" y="{body_top:.1f}" '
        f'width="{body_w * scale:.1f}" height="{body_bottom - body_top:.1f}"/>',
        '</g>',
        '<g stroke="#6b4f3a" stroke-width="1.5" fill="#e6d6c4">',
        f'<rect x="{sleeve_left_x:.1f}" y="{sleeve_top:.1f}" '
        f'width="{sleeve_w * scale:.1f}" height="{sleeve_bottom - sleeve_top:.1f}"/>',
        f'<rect x="{sleeve_right_x:.1f}" y="{sleeve_top:.1f}" '
        f'width="{sleeve_w * scale:.1f}" height="{sleeve_bottom - sleeve_top:.1f}"/>',
        '</g>',
        '<g stroke="#b08b6e" stroke-width="0.8" stroke-dasharray="4 3">',
        f'<line x1="{cx:.1f}" y1="{top:.1f}" x2="{cx:.1f}" y2="{body_bottom:.1f}"/>',
        '</g>',
        '<g font-family="Helvetica, sans-serif" font-size="12" fill="#3a2a1e">',
        f'<text x="{cx:.1f}" y="{top - 10:.1f}" text-anchor="middle">'
        f"{escape(_label(pattern, 'neck', language))}: {_fmt(pattern, neck)}</text>",
        f'<text x="{cx:.1f}" y="{body_bottom + 24:.1f}" text-anchor="middle">'
        f"{escape(_label(pattern, 'bust', language))}: {_fmt(pattern, bust)}</text>",
        f'<text x="{body_x + body_w * scale + 12:.1f}" '
        f'y="{(body_top + body_bottom) / 2:.1f}">'
        f"{escape(_label(pattern, 'body_length', language))}: "
        f"{_fmt(pattern, body_length)}</text>",
        f'<text x="{sleeve_left_x - 12:.1f}" '
        f'y="{(sleeve_top + sleeve_bottom) / 2:.1f}" text-anchor="end">'
        f"{escape(_label(pattern, 'sleeve_length', language))}: "
        f"{_fmt(pattern, sleeve_length)}</text>",
        f'<text x="{cx + body_half + 12:.1f}" '
        f'y="{top + yoke_depth * scale / 2:.1f}">'
        f"{escape(_label(pattern, 'yoke_depth', language))}: "
        f"{_fmt(pattern, yoke_depth)}</text>",
        f'<text x="{sleeve_left_x + sleeve_w * scale / 2:.1f}" '
        f'y="{sleeve_bottom + 18:.1f}" text-anchor="middle">'
        f"{escape(_label(pattern, 'upper_arm', language))}: "
        f"{_fmt(pattern, upper_arm)}</text>",
        "</g>",
        "</svg>",
    ]
    return "".join(parts)


def _maybe(pattern: Pattern, key: str) -> float | None:
    for measurement in pattern.measurements:
        if measurement.key == key:
            return measurement.value_cm
    return None


def render_flat_schematic_svg(
    pattern: Pattern, *, lang: str | None = None
) -> str:
    language = lang or pattern.params.idioma
    bust = _value(pattern, "bust")
    body_length = _value(pattern, "body_length")
    sleeve_length = _maybe(pattern, "sleeve_length")
    upper_arm = _maybe(pattern, "upper_arm")

    body_w = bust / 2
    sleeve_w = (upper_arm or 0.0) / 2
    total_w = body_w + (2 * sleeve_w if sleeve_length is not None else 0.0)
    max_h = max(body_length, sleeve_length or 0.0)
    width, height = 640.0, 760.0
    margin, label_h = 50.0, 90.0
    scale = min(
        (width - 2 * margin) / total_w,
        (height - 2 * margin - label_h) / max_h,
    )
    cx = width / 2
    top = margin + 30
    body_x = cx - body_w * scale / 2
    body_bottom = top + body_length * scale
    title = t(pattern.meta.title_key, language)
    desc = t("pattern.schematic", language)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img" '
        'aria-labelledby="schematic-title schematic-desc">',
        f'<title id="schematic-title">{escape(title)}</title>',
        f'<desc id="schematic-desc">{escape(desc)}</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<g stroke="#6b4f3a" stroke-width="1.5" fill="#f2e8dc">',
        f'<rect x="{body_x:.1f}" y="{top:.1f}" '
        f'width="{body_w * scale:.1f}" height="{body_length * scale:.1f}"/>',
    ]
    if sleeve_length is not None:
        sleeve_top = top
        sleeve_bottom = top + sleeve_length * scale
        parts.extend(
            [
                f'<rect x="{body_x - sleeve_w * scale:.1f}" y="{sleeve_top:.1f}" '
                f'width="{sleeve_w * scale:.1f}" height="{sleeve_bottom - sleeve_top:.1f}"/>',
                f'<rect x="{body_x + body_w * scale:.1f}" y="{sleeve_top:.1f}" '
                f'width="{sleeve_w * scale:.1f}" height="{sleeve_bottom - sleeve_top:.1f}"/>',
            ]
        )
    parts.append("</g>")
    if pattern.meta.family == "cardigan":
        parts.extend(
            [
                '<g stroke="#b08b6e" stroke-width="0.8" stroke-dasharray="4 3">',
                f'<line x1="{cx:.1f}" y1="{top:.1f}" x2="{cx:.1f}" y2="{body_bottom:.1f}"/>',
                "</g>",
            ]
        )
    parts.extend(
        [
            '<g font-family="Helvetica, sans-serif" font-size="12" fill="#3a2a1e">',
            f'<text x="{cx:.1f}" y="{top - 10:.1f}" text-anchor="middle">'
            f"{escape(_label(pattern, 'bust', language))}: {_fmt(pattern, bust)}</text>",
            f'<text x="{body_x + body_w * scale + 12:.1f}" '
            f'y="{(top + body_bottom) / 2:.1f}">'
            f"{escape(_label(pattern, 'body_length', language))}: "
            f"{_fmt(pattern, body_length)}</text>",
        ]
    )
    if sleeve_length is not None and upper_arm is not None:
        parts.extend(
            [
                f'<text x="{body_x - sleeve_w * scale / 2:.1f}" '
                f'y="{top + sleeve_length * scale + 18:.1f}" text-anchor="middle">'
                f"{escape(_label(pattern, 'sleeve_length', language))}: "
                f"{_fmt(pattern, sleeve_length)}</text>",
                f'<text x="{body_x - sleeve_w * scale / 2:.1f}" '
                f'y="{top + sleeve_length * scale + 34:.1f}" text-anchor="middle">'
                f"{escape(_label(pattern, 'upper_arm', language))}: "
                f"{_fmt(pattern, upper_arm)}</text>",
            ]
        )
    parts.extend(["</g>", "</svg>"])
    return "".join(parts)


ACCESSORY_FAMILIES = {
    "hat",
    "scarf",
    "cowl",
    "mittens",
    "socks",
    "shawl",
    "blanket",
    "amigurumi",
    "granny_square",
    "crochet_scarf",
    "bag",
    "crochet_bag",
    "flat_piece",
    "crochet_flat_piece",
}


def _first_measure(pattern: Pattern, keys: tuple[str, ...]) -> tuple[str, float] | None:
    for key in keys:
        value = _maybe(pattern, key)
        if value is not None:
            return key, value
    return None


def _mitten_schematic_svg(pattern: Pattern, language: str) -> str:
    palm = _value(pattern, "palm")
    length = _value(pattern, "length")
    thumb = _maybe(pattern, "thumb") or 6.0
    width, height = 640.0, 760.0
    margin, label_h = 60.0, 110.0
    scale = min(
        (width - 2 * margin) / (palm * 1.35),
        (height - 2 * margin - label_h) / length,
    )
    hand_w = palm * scale
    hand_h = length * scale
    thumb_w = max(22.0, hand_w * 0.22)
    thumb_h = max(28.0, thumb * scale)
    x = (width - hand_w - thumb_w * 0.3) / 2
    y = margin + 30.0
    thumb_x = x + hand_w - thumb_w * 0.6
    thumb_y = y + hand_h - thumb_h - hand_h * 0.18
    title = t(pattern.meta.title_key, language)
    desc = t("pattern.schematic", language)
    hand_path = (
        f"M {x + hand_w * 0.12:.1f} {y + hand_h:.1f} "
        f"L {x + hand_w * 0.08:.1f} {y + hand_h * 0.55:.1f} "
        f"Q {x + hand_w * 0.06:.1f} {y:.1f} {x + hand_w * 0.5:.1f} {y:.1f} "
        f"Q {x + hand_w * 0.94:.1f} {y:.1f} {x + hand_w * 0.92:.1f} "
        f"{y + hand_h * 0.55:.1f} "
        f"L {x + hand_w * 0.88:.1f} {y + hand_h:.1f} Z"
    )
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img" '
        'aria-labelledby="schematic-title schematic-desc">',
        f'<title id="schematic-title">{escape(title)}</title>',
        f'<desc id="schematic-desc">{escape(desc)}</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<rect x="50" y="50" width="540" height="660" fill="none" '
        'stroke="#e5d8ca" stroke-width="1"/>',
        f'<rect x="{thumb_x:.1f}" y="{thumb_y:.1f}" width="{thumb_w:.1f}" '
        f'height="{thumb_h:.1f}" rx="{thumb_w / 2:.1f}" fill="#e6d6c4" '
        'stroke="#6b4f3a" stroke-width="1.5"/>',
        f'<path d="{hand_path}" fill="#f2e8dc" stroke="#6b4f3a" '
        'stroke-width="1.5"/>',
        '<g stroke="#b08b6e" stroke-width="0.8" stroke-dasharray="4 3">',
        f'<line x1="{x + hand_w * 0.12:.1f}" y1="{y + hand_h * 0.86:.1f}" '
        f'x2="{x + hand_w * 0.88:.1f}" y2="{y + hand_h * 0.86:.1f}"/>',
        "</g>",
        '<g font-family="Helvetica, sans-serif" font-size="12" fill="#3a2a1e">',
        f'<text x="{width / 2:.1f}" y="{y - 12:.1f}" text-anchor="middle">'
        f"{escape(_label(pattern, 'palm', language))}: {escape(_fmt(pattern, palm))}</text>",
        f'<text x="{x + hand_w + 14:.1f}" y="{y + hand_h * 0.5:.1f}">'
        f"{escape(_label(pattern, 'length', language))}: {escape(_fmt(pattern, length))}</text>",
        f'<text x="{thumb_x + thumb_w / 2:.1f}" y="{y + hand_h + 42:.1f}" '
        'text-anchor="middle">'
        f"{escape(_label(pattern, 'thumb', language))}: {escape(_fmt(pattern, thumb))}</text>",
        "</g>",
        "</svg>",
    ]
    return "".join(parts)


def render_accessory_schematic_svg(
    pattern: Pattern, *, lang: str | None = None
) -> str:
    language = lang or pattern.params.idioma
    if pattern.meta.family == "mittens":
        return _mitten_schematic_svg(pattern, language)
    width_measure = _first_measure(
        pattern, ("width", "diameter", "circumference", "palm", "head")
    )
    length_measure = _first_measure(
        pattern, ("length", "height", "foot_length", "body_length")
    )
    if width_measure is None or length_measure is None:
        raise KeyError("el accesorio no tiene medidas de ancho y largo")
    width_key, width_cm = width_measure
    length_key, length_cm = length_measure
    width, height = 640.0, 760.0
    margin, label_h = 50.0, 100.0
    scale = min(
        (width - 2 * margin) / width_cm,
        (height - 2 * margin - label_h) / length_cm,
    )
    rect_w = width_cm * scale
    rect_h = length_cm * scale
    x = (width - rect_w) / 2
    y = margin + 30
    title = t(pattern.meta.title_key, language)
    desc = t("pattern.schematic", language)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img" '
        'aria-labelledby="schematic-title schematic-desc">',
        f'<title id="schematic-title">{escape(title)}</title>',
        f'<desc id="schematic-desc">{escape(desc)}</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<rect x="50" y="50" width="540" height="660" fill="none" '
        'stroke="#e5d8ca" stroke-width="1"/>',
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{rect_w:.1f}" '
        f'height="{rect_h:.1f}" fill="#f2e8dc" stroke="#6b4f3a" '
        'stroke-width="1.5"/>',
        '<g font-family="Helvetica, sans-serif" font-size="12" fill="#3a2a1e">',
        f'<text x="{width / 2:.1f}" y="{y - 10:.1f}" text-anchor="middle">'
        f"{escape(_label(pattern, width_key, language))}: "
        f"{escape(_fmt(pattern, width_cm))}</text>",
        f'<text x="{x + rect_w + 12:.1f}" y="{y + rect_h / 2:.1f}">'
        f"{escape(_label(pattern, length_key, language))}: "
        f"{escape(_fmt(pattern, length_cm))}</text>",
        "</g>",
        "</svg>",
    ]
    return "".join(parts)


def render_schematic_svg(pattern: Pattern, *, lang: str | None = None) -> str:
    if pattern.meta.family == "raglan_top_down":
        return render_raglan_schematic_svg(pattern, lang=lang)
    if pattern.meta.family in ACCESSORY_FAMILIES:
        return render_accessory_schematic_svg(pattern, lang=lang)
    return render_flat_schematic_svg(pattern, lang=lang)
