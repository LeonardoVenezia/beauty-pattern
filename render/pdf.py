"""PDF del patron con ReportLab (texto y esquema simple)."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

from engine.i18n import t
from engine.ir import Pattern
from engine.text import render_pattern_text


def _measure(pattern: Pattern, key: str) -> float:
    for measurement in pattern.measurements:
        if measurement.key == key:
            return measurement.value_cm
    raise KeyError(f"falta la medida {key!r}")


def _schematic_drawing(pattern: Pattern, lang: str) -> Drawing:
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
