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


def _panel_texture_svg(
    pattern: Pattern,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    columns: int = 9,
    rows: int = 9,
) -> list[str]:
    crochet = pattern.meta.family.startswith("crochet")
    cell_w = w / columns
    cell_h = h / rows
    size = min(cell_w, cell_h) * 0.24
    parts = ['<g stroke="#cdb59d" stroke-width="0.8" fill="none">']
    for row in range(rows):
        for column in range(columns):
            cx = x + (column + 0.5) * cell_w
            cy = y + (row + 0.5) * cell_h
            if crochet:
                parts.append(
                    f'<path d="M {cx - size:.1f} {cy - size:.1f} '
                    f'L {cx + size:.1f} {cy + size:.1f} '
                    f'M {cx + size:.1f} {cy - size:.1f} '
                    f'L {cx - size:.1f} {cy + size:.1f}"/>'
                )
            else:
                parts.append(
                    f'<path d="M {cx - size:.1f} {cy - size:.1f} '
                    f'L {cx:.1f} {cy + size:.1f} '
                    f'L {cx + size:.1f} {cy - size:.1f}"/>'
                )
    parts.append("</g>")
    return parts


def _bag_schematic_svg(pattern: Pattern, language: str) -> str:
    width_cm = _value(pattern, "width")
    length_cm = _value(pattern, "length")
    width, height = 640.0, 760.0
    scale = min(360.0 / width_cm, 360.0 / length_cm)
    body_w = width_cm * scale
    body_h = length_cm * scale
    x = (width - body_w) / 2
    top = 190.0 + (360.0 - body_h) / 2
    bottom = top + body_h
    handle_top = top - 78.0
    radius = 16.0
    clip_id = f"bag-body-{pattern.meta.id}"
    body_path = (
        f"M {x:.1f} {top:.1f} "
        f"L {x + body_w:.1f} {top:.1f} "
        f"L {x + body_w:.1f} {bottom - radius:.1f} "
        f"Q {x + body_w:.1f} {bottom:.1f} {x + body_w - radius:.1f} {bottom:.1f} "
        f"L {x + radius:.1f} {bottom:.1f} "
        f"Q {x:.1f} {bottom:.1f} {x:.1f} {bottom - radius:.1f} Z"
    )
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
        f'<defs><clipPath id="{escape(clip_id)}">'
        f'<path d="{body_path}"/></clipPath></defs>',
    ]
    for index, stroke in ((0, "#cbb49f"), (1, "#8a6a50")):
        inset = 0.04 * (1 - index)
        hx1 = x + body_w * (0.20 + inset)
        hx2 = x + body_w * (0.80 - inset)
        hy = handle_top + index * 14.0
        parts.append(
            f'<path d="M {hx1:.1f} {top + 8:.1f} '
            f'L {hx1:.1f} {hy + 24:.1f} '
            f'Q {hx1:.1f} {hy:.1f} {hx1 + 18:.1f} {hy:.1f} '
            f'L {hx2 - 18:.1f} {hy:.1f} '
            f'Q {hx2:.1f} {hy:.1f} {hx2:.1f} {hy + 24:.1f} '
            f'L {hx2:.1f} {top + 8:.1f}" '
            f'fill="none" stroke="{stroke}" stroke-width="9" '
            'stroke-linecap="round" stroke-dasharray="10 6"/>'
        )
    parts.extend(
        [
            f'<path d="{body_path}" fill="#f2e8dc" stroke="#6b4f3a" '
            'stroke-width="1.5"/>',
            f'<g clip-path="url(#{escape(clip_id)})">',
        ]
    )
    parts.extend(
        _panel_texture_svg(
            pattern,
            x + 14.0,
            top + 14.0,
            body_w - 28.0,
            body_h - 28.0,
        )
    )
    parts.append(
        f'<line x1="{x + 8:.1f}" y1="{top + body_h * 0.14:.1f}" '
        f'x2="{x + body_w - 8:.1f}" y2="{top + body_h * 0.14:.1f}" '
        'stroke="#b08b6e" stroke-width="0.9" stroke-dasharray="5 4"/>'
    )
    parts.append("</g>")
    for hx in (
        x + body_w * 0.20,
        x + body_w * 0.80,
        x + body_w * 0.24,
        x + body_w * 0.76,
    ):
        parts.append(
            f'<rect x="{hx - 5:.1f}" y="{top - 4:.1f}" width="10" height="8" '
            'rx="2" fill="#6b4f3a"/>'
        )
    parts.extend(
        [
            f'<line x1="{x + 8:.1f}" y1="{top + 18:.1f}" '
            f'x2="{x + 8:.1f}" y2="{bottom - 8:.1f}" '
            'stroke="#d8c3ac" stroke-width="0.8" stroke-dasharray="4 4"/>',
            f'<line x1="{x + body_w - 8:.1f}" y1="{top + 18:.1f}" '
            f'x2="{x + body_w - 8:.1f}" y2="{bottom - 8:.1f}" '
            'stroke="#d8c3ac" stroke-width="0.8" stroke-dasharray="4 4"/>',
            f'<line x1="{x + 8:.1f}" y1="{bottom - 8:.1f}" '
            f'x2="{x + body_w - 8:.1f}" y2="{bottom - 8:.1f}" '
            'stroke="#d8c3ac" stroke-width="0.8" stroke-dasharray="4 4"/>',
            f'<text x="{x + 10:.1f}" y="{top + body_h * 0.14 - 7:.1f}" '
            'font-family="Helvetica, sans-serif" font-size="9" '
            f'fill="#8a6a50">{escape(t("schematic.fold", language))}</text>',
            '<g font-family="Helvetica, sans-serif" font-size="12" fill="#3a2a1e">',
            f'<text x="{width / 2:.1f}" y="{handle_top - 24:.1f}" '
            'text-anchor="middle">'
            f'{escape(t("schematic.optional_handles", language))}</text>',
            f'<line x1="{x:.1f}" y1="{bottom + 22:.1f}" '
            f'x2="{x + body_w:.1f}" y2="{bottom + 22:.1f}" '
            'stroke="#6b4f3a" stroke-width="0.8"/>',
            f'<line x1="{x:.1f}" y1="{bottom + 17:.1f}" '
            f'x2="{x:.1f}" y2="{bottom + 27:.1f}" '
            'stroke="#6b4f3a" stroke-width="0.8"/>',
            f'<line x1="{x + body_w:.1f}" y1="{bottom + 17:.1f}" '
            f'x2="{x + body_w:.1f}" y2="{bottom + 27:.1f}" '
            'stroke="#6b4f3a" stroke-width="0.8"/>',
            f'<text x="{width / 2:.1f}" y="{bottom + 42:.1f}" '
            'text-anchor="middle">'
            f"{escape(_label(pattern, 'width', language))}: "
            f"{escape(_fmt(pattern, width_cm))}</text>",
            f'<line x1="{x + body_w + 18:.1f}" y1="{top:.1f}" '
            f'x2="{x + body_w + 18:.1f}" y2="{bottom:.1f}" '
            'stroke="#6b4f3a" stroke-width="0.8"/>',
            f'<text x="{x + body_w + 26:.1f}" '
            f'y="{(top + bottom) / 2:.1f}">'
            f"{escape(_label(pattern, 'length', language))}: "
            f"{escape(_fmt(pattern, length_cm))}</text>",
            "</g>",
            "</svg>",
        ]
    )
    return "".join(parts)


def _granny_schematic_svg(pattern: Pattern, language: str) -> str:
    width_cm = _value(pattern, "width")
    length_cm = _value(pattern, "length")
    width, height = 640.0, 760.0
    scale = min(360.0 / width_cm, 360.0 / length_cm)
    side_w = width_cm * scale
    side_h = length_cm * scale
    x = (width - side_w) / 2
    y = 190.0 + (360.0 - side_h) / 2
    clip_id = f"granny-body-{pattern.meta.id}"
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
        f'<defs><clipPath id="{escape(clip_id)}">'
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{side_w:.1f}" '
        f'height="{side_h:.1f}" rx="6"/></clipPath></defs>',
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{side_w:.1f}" '
        f'height="{side_h:.1f}" rx="6" fill="#f2e8dc" '
        'stroke="#6b4f3a" stroke-width="1.5"/>',
        f'<rect x="{x + 10:.1f}" y="{y + 10:.1f}" width="{side_w - 20:.1f}" '
        f'height="{side_h - 20:.1f}" rx="4" fill="#e6d6c4" '
        'stroke="#8a6a50" stroke-width="0.8" stroke-dasharray="6 4"/>',
        f'<g clip-path="url(#{escape(clip_id)})">',
    ]
    parts.extend(
        _panel_texture_svg(
            pattern,
            x + 22.0,
            y + 22.0,
            side_w - 44.0,
            side_h - 44.0,
            columns=8,
            rows=8,
        )
    )
    for inset in (0.16, 0.28, 0.40):
        parts.append(
            f'<rect x="{x + side_w * inset:.1f}" y="{y + side_h * inset:.1f}" '
            f'width="{side_w * (1 - 2 * inset):.1f}" '
            f'height="{side_h * (1 - 2 * inset):.1f}" fill="none" '
            'stroke="#c9ad91" stroke-width="0.9" stroke-dasharray="5 4"/>'
        )
    parts.append("</g>")
    for corner_x in (x + 10, x + side_w - 10):
        for corner_y in (y + 10, y + side_h - 10):
            parts.append(
                f'<circle cx="{corner_x:.1f}" cy="{corner_y:.1f}" r="4" '
                'fill="#8a6a50"/>'
            )
    parts.extend(
        [
            '<g font-family="Helvetica, sans-serif" font-size="12" fill="#3a2a1e">',
            f'<text x="{width / 2:.1f}" y="{y - 16:.1f}" text-anchor="middle">'
            f'{escape(t("schematic.granny_base", language))}</text>',
            f'<line x1="{x:.1f}" y1="{y + side_h + 22:.1f}" '
            f'x2="{x + side_w:.1f}" y2="{y + side_h + 22:.1f}" '
            'stroke="#6b4f3a" stroke-width="0.8"/>',
            f'<line x1="{x:.1f}" y1="{y + side_h + 17:.1f}" '
            f'x2="{x:.1f}" y2="{y + side_h + 27:.1f}" '
            'stroke="#6b4f3a" stroke-width="0.8"/>',
            f'<line x1="{x + side_w:.1f}" y1="{y + side_h + 17:.1f}" '
            f'x2="{x + side_w:.1f}" y2="{y + side_h + 27:.1f}" '
            'stroke="#6b4f3a" stroke-width="0.8"/>',
            f'<text x="{width / 2:.1f}" y="{y + side_h + 42:.1f}" '
            'text-anchor="middle">'
            f"{escape(_label(pattern, 'width', language))}: "
            f"{escape(_fmt(pattern, width_cm))}</text>",
            f'<line x1="{x + side_w + 18:.1f}" y1="{y:.1f}" '
            f'x2="{x + side_w + 18:.1f}" y2="{y + side_h:.1f}" '
            'stroke="#6b4f3a" stroke-width="0.8"/>',
            f'<text x="{x + side_w + 26:.1f}" '
            f'y="{y + side_h / 2:.1f}">'
            f"{escape(_label(pattern, 'length', language))}: "
            f"{escape(_fmt(pattern, length_cm))}</text>",
            "</g>",
            "</svg>",
        ]
    )
    return "".join(parts)


def render_accessory_schematic_svg(
    pattern: Pattern, *, lang: str | None = None
) -> str:
    language = lang or pattern.params.idioma
    if pattern.meta.family == "mittens":
        return _mitten_schematic_svg(pattern, language)
    if pattern.meta.family in {"bag", "crochet_bag"}:
        return _bag_schematic_svg(pattern, language)
    if pattern.meta.family == "granny_square":
        return _granny_schematic_svg(pattern, language)
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
