"""PDF del patron con ReportLab (texto y esquema simple)."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Ellipse, Line, Path, Polygon, Rect, String
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

from engine.i18n import t
from engine.ir import Pattern
from engine.text import render_pattern_text
from render.schematic import ACCESSORY_FAMILIES


def _measure(pattern: Pattern, key: str) -> float:
    for measurement in pattern.measurements:
        if measurement.key == key:
            return measurement.value_cm
    raise KeyError(f"falta la medida {key!r}")


def _schematic_drawing(pattern: Pattern, lang: str) -> Drawing:
    if pattern.meta.family == "mittens":
        return _mitten_drawing(pattern, lang)
    if pattern.meta.family in ACCESSORY_FAMILIES:
        return _accessory_drawing(pattern, lang)
    if pattern.meta.family != "raglan_top_down":
        return _flat_drawing(pattern, lang)
    bust = _measure(pattern, "bust")
    body_length = _measure(pattern, "body_length")
    sleeve_length = _measure(pattern, "sleeve_length")
    upper_arm = _measure(pattern, "upper_arm")
    yoke_depth = _measure(pattern, "yoke_depth")
    body_w = bust / 2
    sleeve_w = upper_arm / 2
    total_w = body_w + 2 * sleeve_w
    max_h = max(body_length, sleeve_length)
    width, height = 360.0, 260.0
    scale = min(width / total_w, height / max_h)
    cx = width / 2
    top = 18.0
    body_top = top + yoke_depth * scale
    body_bottom = body_top + (body_length - yoke_depth) * scale
    body_x = cx - body_w * scale / 2
    sleeve_top = body_top
    sleeve_bottom = sleeve_top + (sleeve_length - yoke_depth) * scale
    sleeve_left_x = body_x - sleeve_w * scale
    sleeve_right_x = body_x + body_w * scale
    neck_half = _measure(pattern, "neck") / 2 * scale
    body_half = body_w / 2 * scale

    drawing = Drawing(width, height)
    drawing.add(
        Polygon(
            [
                cx - neck_half,
                height - top,
                cx + neck_half,
                height - top,
                cx + body_half,
                height - body_top,
                cx - body_half,
                height - body_top,
            ],
            fillColor="#f2e8dc",
            strokeColor="#6b4f3a",
        )
    )
    drawing.add(
        Rect(
            body_x,
            height - body_bottom,
            body_w * scale,
            body_bottom - body_top,
            fillColor="#f2e8dc",
            strokeColor="#6b4f3a",
        )
    )
    for x in (sleeve_left_x, sleeve_right_x):
        drawing.add(
            Rect(
                x,
                height - sleeve_bottom,
                sleeve_w * scale,
                sleeve_bottom - sleeve_top,
                fillColor="#e6d6c4",
                strokeColor="#6b4f3a",
            )
        )
    drawing.add(
        Line(
            cx,
            height - top,
            cx,
            height - body_bottom,
            strokeColor="#b08b6e",
            strokeDashArray=[4, 3],
        )
    )
    labels = (
        ("neck", _measure(pattern, "neck"), cx, height - top + 10, "middle"),
        ("bust", bust, cx, height - body_bottom - 10, "middle"),
        (
            "body_length",
            body_length,
            body_x + body_w * scale + 6,
            height - (body_top + body_bottom) / 2,
            "start",
        ),
        (
            "sleeve_length",
            sleeve_length,
            sleeve_left_x - 6,
            height - (sleeve_top + sleeve_bottom) / 2,
            "end",
        ),
        (
            "yoke_depth",
            yoke_depth,
            cx + body_half + 6,
            height - (top + yoke_depth * scale / 2),
            "start",
        ),
    )
    for key, value, x, y, anchor in labels:
        text = f"{t(f'measure.{key}', lang)}: {value:.1f} cm"
        drawing.add(
            String(
                x,
                y,
                text,
                fontName="Helvetica",
                fontSize=7,
                fillColor="#3a2a1e",
                textAnchor=anchor,
            )
        )
    return drawing


def _maybe_measure(pattern: Pattern, key: str) -> float | None:
    for measurement in pattern.measurements:
        if measurement.key == key:
            return measurement.value_cm
    return None


def _mitten_drawing(pattern: Pattern, lang: str) -> Drawing:
    palm = _measure(pattern, "palm")
    length = _measure(pattern, "length")
    thumb = _maybe_measure(pattern, "thumb") or 6.0
    width, height = 360.0, 280.0
    scale = min((width - 70.0) / (palm * 1.35), (height - 60.0) / length)
    hand_w = palm * scale
    hand_h = length * scale
    thumb_w = max(17.0, hand_w * 0.22)
    thumb_h = max(20.0, thumb * scale)
    x = (width - hand_w - thumb_w * 0.3) / 2
    y = 18.0
    thumb_x = x + hand_w - thumb_w * 0.6
    thumb_y = y + hand_h - thumb_h - hand_h * 0.18
    drawing = Drawing(width, height)
    drawing.add(
        Ellipse(
            thumb_x + thumb_w / 2,
            height - (thumb_y + thumb_h / 2),
            thumb_w / 2,
            thumb_h / 2,
            fillColor="#e6d6c4",
            strokeColor="#6b4f3a",
        )
    )
    hand_path = Path(fillColor="#f2e8dc", strokeColor="#6b4f3a", strokeWidth=1)
    hand_path.moveTo(x + hand_w * 0.12, height - (y + hand_h))
    hand_path.lineTo(x + hand_w * 0.08, height - (y + hand_h * 0.55))
    hand_path.curveTo(
        x + hand_w * 0.06,
        height - y,
        x + hand_w * 0.5,
        height - y,
        x + hand_w * 0.5,
        height - y,
    )
    hand_path.curveTo(
        x + hand_w * 0.94,
        height - y,
        x + hand_w * 0.92,
        height - (y + hand_h * 0.55),
        x + hand_w * 0.92,
        height - (y + hand_h * 0.55),
    )
    hand_path.lineTo(x + hand_w * 0.88, height - (y + hand_h))
    hand_path.closePath()
    drawing.add(hand_path)
    drawing.add(
        Line(
            x + hand_w * 0.12,
            height - (y + hand_h * 0.86),
            x + hand_w * 0.88,
            height - (y + hand_h * 0.86),
            strokeColor="#b08b6e",
            strokeDashArray=[4, 3],
        )
    )
    labels = (
        (
            "palm",
            palm,
            width / 2,
            height - y + 10,
            "middle",
        ),
        (
            "length",
            length,
            x + hand_w + 8,
            height - (y + hand_h / 2),
            "start",
        ),
        (
            "thumb",
            thumb,
            thumb_x + thumb_w / 2,
            height - (y + hand_h) - 18,
            "middle",
        ),
    )
    for key, value, lx, ly, anchor in labels:
        drawing.add(
            String(
                lx,
                ly,
                f"{t(f'measure.{key}', lang)}: {value:.1f} cm",
                fontName="Helvetica",
                fontSize=7,
                fillColor="#3a2a1e",
                textAnchor=anchor,
            )
        )
    return drawing


def _accessory_drawing(pattern: Pattern, lang: str) -> Drawing:
    width_measure = next(
        (
            (key, value)
            for key in ("width", "diameter", "circumference", "palm", "head")
            if (value := _maybe_measure(pattern, key)) is not None
        ),
        None,
    )
    length_measure = next(
        (
            (key, value)
            for key in ("length", "height", "foot_length", "body_length")
            if (value := _maybe_measure(pattern, key)) is not None
        ),
        None,
    )
    if width_measure is None or length_measure is None:
        raise KeyError("el accesorio no tiene medidas de ancho y largo")
    width_key, width_cm = width_measure
    length_key, length_cm = length_measure
    width, height = 360.0, 280.0
    scale = min((width - 40.0) / width_cm, (height - 50.0) / length_cm)
    rect_w = width_cm * scale
    rect_h = length_cm * scale
    x = (width - rect_w) / 2
    y = 24.0
    drawing = Drawing(width, height)
    drawing.add(
        Rect(
            x,
            height - y - rect_h,
            rect_w,
            rect_h,
            fillColor="#f2e8dc",
            strokeColor="#6b4f3a",
        )
    )
    drawing.add(
        String(
            width / 2,
            height - y + 10,
            f"{t(f'measure.{width_key}', lang)}: {width_cm:.1f} cm",
            fontName="Helvetica",
            fontSize=7,
            fillColor="#3a2a1e",
            textAnchor="middle",
        )
    )
    drawing.add(
        String(
            x + rect_w + 6,
            height - y - rect_h / 2,
            f"{t(f'measure.{length_key}', lang)}: {length_cm:.1f} cm",
            fontName="Helvetica",
            fontSize=7,
            fillColor="#3a2a1e",
            textAnchor="start",
        )
    )
    return drawing


def _flat_drawing(pattern: Pattern, lang: str) -> Drawing:
    bust = _measure(pattern, "bust")
    body_length = _measure(pattern, "body_length")
    sleeve_length = _maybe_measure(pattern, "sleeve_length")
    upper_arm = _maybe_measure(pattern, "upper_arm")
    body_w = bust / 2
    sleeve_w = (upper_arm or 0.0) / 2
    total_w = body_w + (2 * sleeve_w if sleeve_length is not None else 0.0)
    max_h = max(body_length, sleeve_length or 0.0)
    width, height = 360.0, 280.0
    scale = min(width / total_w, (height - 30.0) / max_h)
    cx = width / 2
    top = 18.0
    body_x = cx - body_w * scale / 2
    body_bottom = top + body_length * scale
    drawing = Drawing(width, height)
    drawing.add(
        Rect(
            body_x,
            height - body_bottom,
            body_w * scale,
            body_length * scale,
            fillColor="#f2e8dc",
            strokeColor="#6b4f3a",
        )
    )
    if sleeve_length is not None:
        sleeve_w_px = sleeve_w * scale
        sleeve_h = sleeve_length * scale
        for x in (body_x - sleeve_w_px, body_x + body_w * scale):
            drawing.add(
                Rect(
                    x,
                    height - top - sleeve_h,
                    sleeve_w_px,
                    sleeve_h,
                    fillColor="#e6d6c4",
                    strokeColor="#6b4f3a",
                )
            )
    labels = [
        ("bust", bust, cx, height - top + 10, "middle"),
        (
            "body_length",
            body_length,
            body_x + body_w * scale + 6,
            height - (top + body_bottom) / 2,
            "start",
        ),
    ]
    if sleeve_length is not None:
        labels.append(
            (
                "sleeve_length",
                sleeve_length,
                body_x - sleeve_w * scale - 6,
                height - top - sleeve_length * scale / 2,
                "end",
            )
        )
    for key, value, x, y, anchor in labels:
        drawing.add(
            String(
                x,
                y,
                f"{t(f'measure.{key}', lang)}: {value:.1f} cm",
                fontName="Helvetica",
                fontSize=7,
                fillColor="#3a2a1e",
                textAnchor=anchor,
            )
        )
    return drawing


def render_pattern_pdf(
    pattern: Pattern, *, lang: str | None = None
) -> bytes:
    language = lang or pattern.params.idioma
    text = render_pattern_text(pattern, lang=language)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=t(pattern.meta.title_key, language),
        author="Tejedora",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "PatternBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=2,
    )
    heading = ParagraphStyle(
        "PatternHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        spaceAfter=8,
    )
    story: list[Flowable] = []
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            story.append(Spacer(1, 6))
            continue
        style = heading if index == 0 else body
        story.append(Paragraph(escape(line), style))
        if index == 0:
            story.append(Spacer(1, 6))
            story.append(_schematic_drawing(pattern, language))
            story.append(Spacer(1, 12))
    document.build(story)
    return buffer.getvalue()
