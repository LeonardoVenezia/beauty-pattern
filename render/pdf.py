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
    if pattern.meta.family in {"bag", "crochet_bag"}:
        return _bag_drawing(pattern, lang)
    if pattern.meta.family == "granny_square":
        return _granny_drawing(pattern, lang)
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


def _bag_drawing(pattern: Pattern, lang: str) -> Drawing:
    width_cm = _measure(pattern, "width")
    length_cm = _measure(pattern, "length")
    width, height = 360.0, 330.0
    scale = min(220.0 / width_cm, 210.0 / length_cm)
    body_w = width_cm * scale
    body_h = length_cm * scale
    x = (width - body_w) / 2
    bottom = 38.0
    top = bottom + body_h
    handle_top = top + 62.0
    radius = 10.0
    crochet = pattern.meta.family.startswith("crochet")
    drawing = Drawing(width, height)

    for index, color in ((0, "#cbb49f"), (1, "#8a6a50")):
        inset = 0.04 * (1 - index)
        hx1 = x + body_w * (0.20 + inset)
        hx2 = x + body_w * (0.80 - inset)
        hy = handle_top - index * 10.0
        handle = Path(
            fillColor=None,
            strokeColor=color,
            strokeWidth=6.0 - index,
            strokeDashArray=[7, 4],
        )
        handle.moveTo(hx1, top + 6)
        handle.lineTo(hx1, hy - 16)
        handle.curveTo(hx1, hy, hx1 + 10, hy, hx1 + 16, hy)
        handle.lineTo(hx2 - 16, hy)
        handle.curveTo(hx2, hy, hx2, hy - 16, hx2, hy - 16)
        handle.lineTo(hx2, top + 6)
        drawing.add(handle)

    body = Path(fillColor="#f2e8dc", strokeColor="#6b4f3a", strokeWidth=1.2)
    body.moveTo(x, bottom + radius)
    body.lineTo(x, top)
    body.lineTo(x + body_w, top)
    body.lineTo(x + body_w, bottom + radius)
    body.curveTo(
        x + body_w,
        bottom,
        x + body_w - radius,
        bottom,
        x + body_w - radius,
        bottom,
    )
    body.lineTo(x + radius, bottom)
    body.curveTo(x, bottom, x, bottom + radius, x, bottom + radius)
    body.closePath()
    drawing.add(body)

    texture_x = x + 14.0
    texture_y = bottom + 14.0
    texture_w = body_w - 28.0
    texture_h = body_h - 28.0
    columns, rows = 9, 9
    cell_w = texture_w / columns
    cell_h = texture_h / rows
    size = min(cell_w, cell_h) * 0.24
    for row in range(rows):
        for column in range(columns):
            cx = texture_x + (column + 0.5) * cell_w
            cy = texture_y + (row + 0.5) * cell_h
            if crochet:
                drawing.add(
                    Line(
                        cx - size,
                        cy - size,
                        cx + size,
                        cy + size,
                        strokeColor="#cdb59d",
                        strokeWidth=0.5,
                    )
                )
                drawing.add(
                    Line(
                        cx + size,
                        cy - size,
                        cx - size,
                        cy + size,
                        strokeColor="#cdb59d",
                        strokeWidth=0.5,
                    )
                )
            else:
                drawing.add(
                    Line(
                        cx - size,
                        cy + size,
                        cx,
                        cy - size,
                        strokeColor="#cdb59d",
                        strokeWidth=0.5,
                    )
                )
                drawing.add(
                    Line(
                        cx,
                        cy - size,
                        cx + size,
                        cy + size,
                        strokeColor="#cdb59d",
                        strokeWidth=0.5,
                    )
                )

    for hx in (
        x + body_w * 0.20,
        x + body_w * 0.80,
        x + body_w * 0.24,
        x + body_w * 0.76,
    ):
        drawing.add(
            Rect(
                hx - 4,
                top - 3,
                8,
                6,
                rx=2,
                fillColor="#6b4f3a",
                strokeColor=None,
            )
        )

    hem_y = top - body_h * 0.14
    drawing.add(
        Line(
            x + 8,
            hem_y,
            x + body_w - 8,
            hem_y,
            strokeColor="#b08b6e",
            strokeWidth=0.8,
            strokeDashArray=[4, 3],
        )
    )
    for sx in (x + 8, x + body_w - 8):
        drawing.add(
            Line(
                sx,
                top - 16,
                sx,
                bottom + 8,
                strokeColor="#d8c3ac",
                strokeWidth=0.7,
                strokeDashArray=[3, 3],
            )
        )
    drawing.add(
        Line(
            x + 8,
            bottom + 8,
            x + body_w - 8,
            bottom + 8,
            strokeColor="#d8c3ac",
            strokeWidth=0.7,
            strokeDashArray=[3, 3],
        )
    )

    drawing.add(
        String(
            x + 10,
            hem_y - 7,
            t("schematic.fold", lang),
            fontName="Helvetica",
            fontSize=6,
            fillColor="#8a6a50",
        )
    )
    drawing.add(
        String(
            width / 2,
            handle_top + 10,
            t("schematic.optional_handles", lang),
            fontName="Helvetica",
            fontSize=6,
            fillColor="#3a2a1e",
            textAnchor="middle",
        )
    )
    drawing.add(
        Line(
            x,
            bottom - 18,
            x + body_w,
            bottom - 18,
            strokeColor="#6b4f3a",
            strokeWidth=0.7,
        )
    )
    for tx in (x, x + body_w):
        drawing.add(
            Line(
                tx,
                bottom - 22,
                tx,
                bottom - 14,
                strokeColor="#6b4f3a",
                strokeWidth=0.7,
            )
        )
    drawing.add(
        String(
            width / 2,
            bottom - 28,
            f"{t('measure.width', lang)}: {width_cm:.1f} cm",
            fontName="Helvetica",
            fontSize=7,
            fillColor="#3a2a1e",
            textAnchor="middle",
        )
    )
    drawing.add(
        Line(
            x + body_w + 16,
            top,
            x + body_w + 16,
            bottom,
            strokeColor="#6b4f3a",
            strokeWidth=0.7,
        )
    )
    drawing.add(
        String(
            x + body_w + 22,
            (top + bottom) / 2,
            f"{t('measure.length', lang)}: {length_cm:.1f} cm",
            fontName="Helvetica",
            fontSize=7,
            fillColor="#3a2a1e",
        )
    )
    return drawing


def _granny_drawing(pattern: Pattern, lang: str) -> Drawing:
    width_cm = _measure(pattern, "width")
    length_cm = _measure(pattern, "length")
    width, height = 360.0, 300.0
    scale = min(220.0 / width_cm, 220.0 / length_cm)
    side_w = width_cm * scale
    side_h = length_cm * scale
    x = (width - side_w) / 2
    y = 40.0
    top = y + side_h
    drawing = Drawing(width, height)
    drawing.add(
        Rect(
            x,
            y,
            side_w,
            side_h,
            rx=4,
            fillColor="#f2e8dc",
            strokeColor="#6b4f3a",
            strokeWidth=1.2,
        )
    )
    drawing.add(
        Rect(
            x + 7,
            y + 7,
            side_w - 14,
            side_h - 14,
            rx=3,
            fillColor=None,
            strokeColor="#8a6a50",
            strokeWidth=0.7,
            strokeDashArray=[4, 3],
        )
    )
    texture_x = x + 16.0
    texture_y = y + 16.0
    texture_w = side_w - 32.0
    texture_h = side_h - 32.0
    columns, rows = 8, 8
    cell_w = texture_w / columns
    cell_h = texture_h / rows
    size = min(cell_w, cell_h) * 0.24
    for row in range(rows):
        for column in range(columns):
            cx = texture_x + (column + 0.5) * cell_w
            cy = texture_y + (row + 0.5) * cell_h
            drawing.add(
                Line(
                    cx - size,
                    cy - size,
                    cx + size,
                    cy + size,
                    strokeColor="#cdb59d",
                    strokeWidth=0.5,
                )
            )
            drawing.add(
                Line(
                    cx + size,
                    cy - size,
                    cx - size,
                    cy + size,
                    strokeColor="#cdb59d",
                    strokeWidth=0.5,
                )
            )
    for inset in (0.16, 0.28, 0.40):
        drawing.add(
            Rect(
                x + side_w * inset,
                y + side_h * inset,
                side_w * (1 - 2 * inset),
                side_h * (1 - 2 * inset),
                fillColor=None,
                strokeColor="#c9ad91",
                strokeWidth=0.6,
                strokeDashArray=[3, 3],
            )
        )
    drawing.add(
        String(
            width / 2,
            top + 12,
            t("schematic.granny_base", lang),
            fontName="Helvetica",
            fontSize=7,
            fillColor="#3a2a1e",
            textAnchor="middle",
        )
    )
    drawing.add(
        Line(
            x,
            y - 18,
            x + side_w,
            y - 18,
            strokeColor="#6b4f3a",
            strokeWidth=0.7,
        )
    )
    for tx in (x, x + side_w):
        drawing.add(
            Line(
                tx,
                y - 22,
                tx,
                y - 14,
                strokeColor="#6b4f3a",
                strokeWidth=0.7,
            )
        )
    drawing.add(
        String(
            width / 2,
            y - 28,
            f"{t('measure.width', lang)}: {width_cm:.1f} cm",
            fontName="Helvetica",
            fontSize=7,
            fillColor="#3a2a1e",
            textAnchor="middle",
        )
    )
    drawing.add(
        Line(
            x + side_w + 16,
            top,
            x + side_w + 16,
            y,
            strokeColor="#6b4f3a",
            strokeWidth=0.7,
        )
    )
    drawing.add(
        String(
            x + side_w + 22,
            (top + y) / 2,
            f"{t('measure.length', lang)}: {length_cm:.1f} cm",
            fontName="Helvetica",
            fontSize=7,
            fillColor="#3a2a1e",
        )
    )
    return drawing


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
