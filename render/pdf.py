"""PDF del patron: portada, materiales, muestra, medidas, esquema e instrucciones.

Usa la misma estructura de bloques que el texto y el mismo SVG de esquema que
la web (convertido a Drawing con svglib) para que haya una sola fuente de
verdad. Los numeros provienen siempre de la IR verificada por el motor.
"""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_CENTER  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import cm  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

try:
    from svglib.svglib import svg2rlg  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - fallback si svglib no esta instalado
    svg2rlg = None  # type: ignore[assignment]

from engine.blocks import (
    BlockKind,
    build_pattern_blocks,
)
from engine.i18n import t
from engine.ir import Pattern
from render.schematic import render_schematic_svg

_INK = colors.HexColor("#3a2a1e")
_SOFT = colors.HexColor("#6b4f3a")
_RULE = colors.HexColor("#d8c3ac")
_PANEL = colors.HexColor("#f6f0e8")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=_INK,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "PSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            textColor=_SOFT,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "PH1",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=_INK,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "PH2",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=_INK,
            spaceBefore=6,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "PBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=_INK,
            spaceAfter=2,
        ),
        "step": ParagraphStyle(
            "PStep",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=_INK,
            leftIndent=14,
            firstLineIndent=-14,
            spaceAfter=3,
        ),
        "bullet": ParagraphStyle(
            "PBullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=_INK,
            leftIndent=12,
            firstLineIndent=-8,
            spaceAfter=2,
        ),
        "small": ParagraphStyle(
            "PSmall",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=_SOFT,
            spaceAfter=2,
        ),
    }


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _schematic_flowable(pattern: Pattern, lang: str, max_width: float) -> Flowable | None:
    if svg2rlg is None:
        return None
    svg = render_schematic_svg(pattern, lang=lang)
    drawing = svg2rlg(BytesIO(svg.encode("utf-8")))
    if drawing is None:
        return None
    scale = min(max_width / drawing.width, (16.0 * cm) / drawing.height, 1.0)
    drawing.width *= scale
    drawing.height *= scale
    drawing.scale(scale, scale)
    return drawing


def _kv_table(rows: list[tuple[str, str]], width: float, styles: dict[str, ParagraphStyle]) -> Table:
    data = [
        [
            Paragraph(f"<b>{_esc(label)}</b>", styles["body"]),
            Paragraph(_esc(value), styles["body"]),
        ]
        for label, value in rows
    ]
    table = Table(data, colWidths=[width * 0.38, width * 0.62], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _PANEL]),
                ("TEXTCOLOR", (0, 0), (-1, -1), _INK),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, _RULE),
                ("BOX", (0, 0), (-1, -1), 0.5, _RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def render_pattern_pdf(pattern: Pattern, *, lang: str | None = None) -> bytes:
    language = lang or pattern.params.idioma
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=t(pattern.meta.title_key, language),
        author="Tejedora",
    )
    styles = _styles()
    frame_w = doc.width

    story: list[Flowable] = []
    story.append(Paragraph(_esc(t(pattern.meta.title_key, language)), styles["title"]))
    story.append(
        Paragraph(
            _esc(
                f"{t('pattern.generated_by', language)} · "
                f"{t('pattern.size', language, size=pattern.meta.size)} · "
                f"{t('pattern.units', language, units=pattern.params.unidades)} · "
                f"{t('pattern.skill', language, level=pattern.params.nivel)}"
            ),
            styles["subtitle"],
        )
    )

    schematic = _schematic_flowable(pattern, language, frame_w)
    if schematic is not None:
        story.append(schematic)
        story.append(Spacer(1, 10))

    blocks = build_pattern_blocks(pattern, lang=language)

    current_section: list[Flowable] = []
    glossary_rows: list[tuple[str, str]] = []

    def flush_section() -> None:
        nonlocal current_section
        if current_section:
            # Mantener encabezado + primer paso juntos si hay espacio.
            keep = 2 if len(current_section) >= 2 else len(current_section)
            story.append(KeepTogether(current_section[:keep]))
            story.extend(current_section[keep:])
            story.append(Spacer(1, 4))
            current_section = []

    def flush_glossary() -> None:
        nonlocal glossary_rows
        if glossary_rows:
            story.append(_kv_table(glossary_rows, frame_w, styles))
            story.append(Spacer(1, 4))
            glossary_rows = []

    for block in blocks:
        if block.kind is BlockKind.TITLE:
            continue
        if block.kind is BlockKind.SUBTITLE:
            story.append(Paragraph(_esc(block.text), styles["small"]))
            continue
        if block.kind is BlockKind.DOC_HEADING:
            flush_section()
            flush_glossary()
            story.append(Paragraph(_esc(block.text), styles["h1"]))
            continue
        if block.kind is BlockKind.SECTION_HEADING:
            flush_glossary()
            flush_section()
            current_section = [Paragraph(_esc(block.text), styles["h2"])]
            continue
        if block.kind is BlockKind.MEASURE:
            flush_glossary()
            if block.label:
                story.append(
                    Paragraph(
                        f"<b>{_esc(block.label)}:</b> {_esc(block.text)}",
                        styles["body"],
                    )
                )
            else:
                story.append(Paragraph(_esc(block.text), styles["body"]))
            continue
        if block.kind is BlockKind.GLOSSARY:
            flush_section()
            if block.label and block.value:
                glossary_rows.append((block.label, block.value))
            else:
                glossary_rows.append((block.text, ""))
            continue
        if block.kind in {BlockKind.STEP, BlockKind.REPEAT}:
            flush_glossary()
            target = current_section if current_section else story
            target.append(Paragraph(f"• {_esc(block.text)}", styles["step"]))
            continue
        if block.kind is BlockKind.WARNING:
            flush_glossary()
            target = current_section if current_section else story
            target.append(Paragraph(f"• {_esc(block.text)}", styles["bullet"]))
            continue
        if block.kind is BlockKind.LINE:
            flush_glossary()
            target = current_section if current_section else story
            target.append(Paragraph(_esc(block.text), styles["body"]))
            continue

    flush_section()
    flush_glossary()

    doc.build(story)
    return buffer.getvalue()
