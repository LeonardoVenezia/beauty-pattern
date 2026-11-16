"""PDF del patron con el formato del estandar de mercado.

Renderiza un `PatternDocument` (engine/document.py): portada, ficha tecnica,
talles, materiales, muestra, abreviaturas, notas, instrucciones, esquema,
terminacion y creditos. Encabezado y pie en cada pagina ("Pagina 3 de 12"),
marcadores del PDF por seccion, metadatos, A4 o Carta, version para imprimir
(sin fondos) y talle resaltado. Los numeros vienen siempre de la IR
verificada; este modulo solo maqueta.
"""

from __future__ import annotations

import re
from dataclasses import replace
from io import BytesIO
from typing import Any, Literal

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_CENTER  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4, LETTER  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-untyped]
from reportlab.lib.units import cm, mm  # type: ignore[import-untyped]
from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.doctemplate import BaseDocTemplate  # type: ignore[import-untyped]

try:
    from svglib.svglib import svg2rlg  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - fallback si svglib no esta instalado
    svg2rlg = None  # type: ignore[assignment]

from engine.blocks import BlockKind
from engine.document import PatternDocument, build_document
from engine.i18n import t
from engine.ir import Pattern
from engine.multisize import NOT_APPLICABLE
from render.chart import render_stitch_chart_svg
from render.schematic import render_schematic_svg

Paper = Literal["A4", "Letter"]

_INK = colors.HexColor("#33261c")
_SOFT = colors.HexColor("#6b5442")
_RULE = colors.HexColor("#d8c3ac")
_PANEL = colors.HexColor("#f6f0e8")
_ACCENT = colors.HexColor("#9c4a2f")


def _styles(print_mode: bool) -> dict[str, ParagraphStyle]:
    def style(name: str, **kw: Any) -> ParagraphStyle:
        base: dict[str, Any] = {"fontName": "Helvetica", "fontSize": 10.5, "leading": 15, "textColor": _INK}
        base.update(kw)
        return ParagraphStyle(name, **base)

    return {
        "cover_title": style("CoverTitle", fontName="Helvetica-Bold", fontSize=30, leading=36, alignment=TA_CENTER),
        "cover_sub": style("CoverSub", fontSize=13, leading=18, textColor=_SOFT, alignment=TA_CENTER),
        "h1": style(
            "H1", fontName="Helvetica-Bold", fontSize=15, leading=19, spaceBefore=12, spaceAfter=5,
            textColor=_INK if print_mode else _ACCENT, keepWithNext=1,
        ),
        "h2": style("H2", fontName="Helvetica-Bold", fontSize=12, leading=16, spaceBefore=9, spaceAfter=3, keepWithNext=1),
        "body": style("Body", spaceAfter=3),
        "step": style("Step", leftIndent=12, firstLineIndent=-12, spaceAfter=4),
        "note": style("Note", fontSize=9.5, leading=13, textColor=_SOFT, leftIndent=10, firstLineIndent=-8, spaceAfter=2),
        "cell": style("Cell", fontSize=9.5, leading=12.5),
        "cell_bold": style("CellBold", fontName="Helvetica-Bold", fontSize=9.5, leading=12.5),
    }


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_VALUE = rf"(?:\d+(?:[.,]\d+)?|{NOT_APPLICABLE})"
_MULTI = re.compile(rf"({_VALUE}) \(({_VALUE}(?:, {_VALUE})*)\)")


def _highlight(text: str, index: int | None, sizes: tuple[str, ...], lang: str) -> str:
    """Escapa y resalta el valor del talle `index` en cada grupo `a (b, c)`."""
    escaped = _esc(text)
    if index is None:
        return escaped
    local = index
    head, sep, rest = t("pattern.only_sizes", lang, sizes="\x00").partition("\x00")
    if escaped.startswith(head) and sep:
        listed, _, _ = escaped[len(head) :].partition(rest)
        present = [s.strip() for s in listed.split(",")]
        if sizes[index] not in present:
            return escaped
        local = present.index(sizes[index])

    def mark(match: re.Match[str]) -> str:
        values = [match.group(1), *[v.strip() for v in match.group(2).split(",")]]
        if local >= len(values):
            return match.group(0)
        values[local] = f'<font color="#9c4a2f"><b>{values[local]}</b></font>'
        return f"{values[0]} ({', '.join(values[1:])})"

    return _MULTI.sub(mark, escaped)


def _svg_drawing(svg: str, max_w: float, max_h: float) -> Flowable | None:
    if svg2rlg is None:
        return None
    drawing = svg2rlg(BytesIO(svg.encode("utf-8")))
    if drawing is None:
        return None
    scale = min(max_w / drawing.width, max_h / drawing.height, 1.6)
    drawing.width *= scale
    drawing.height *= scale
    drawing.scale(scale, scale)
    drawing.hAlign = "CENTER"
    return drawing


def _drawing(
    pattern: Pattern, lang: str, max_w: float, max_h: float, *, letters_only: bool = False
) -> Flowable | None:
    if svg2rlg is None:
        return None
    svg = render_schematic_svg(pattern, lang=lang, letters_only=letters_only)
    drawing = svg2rlg(BytesIO(svg.encode("utf-8")))
    if drawing is None:
        return None
    scale = min(max_w / drawing.width, max_h / drawing.height, 1.0)
    drawing.width *= scale
    drawing.height *= scale
    drawing.scale(scale, scale)
    drawing.hAlign = "CENTER"
    return drawing


def _table(
    rows: tuple[tuple[str, ...], ...],
    width: float,
    styles: dict[str, ParagraphStyle],
    *,
    header: bool,
    highlight_col: int | None,
    print_mode: bool,
) -> Table:
    data = []
    for r, row in enumerate(rows):
        cells = []
        for c, value in enumerate(row):
            bold = (header and r == 0) or c == 0 or (highlight_col is not None and c == highlight_col)
            cells.append(Paragraph(_esc(value), styles["cell_bold" if bold else "cell"]))
        data.append(cells)
    columns = len(rows[0])
    first = width * (0.34 if columns > 2 else 0.30)
    widths = [first] + [(width - first) / (columns - 1)] * (columns - 1)
    table = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1 if header else 0)
    commands: list[tuple[Any, ...]] = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, _RULE),
        ("BOX", (0, 0), (-1, -1), 0.5, _RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if not print_mode:
        commands.append(("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, _PANEL]))
        if header:
            commands.append(("BACKGROUND", (0, 0), (-1, 0), _RULE))
        if highlight_col is not None:
            commands.append(("BACKGROUND", (highlight_col, 0), (highlight_col, -1), colors.HexColor("#f3dccf")))
    elif header:
        commands.append(("LINEBELOW", (0, 0), (-1, 0), 1, _INK))
    table.setStyle(TableStyle(commands))
    return table


class _Doc(BaseDocTemplate):  # type: ignore[misc]
    """Agrega marcadores del PDF (bookmarks) en cada titulo de seccion."""

    def afterFlowable(self, flowable: Flowable) -> None:
        if isinstance(flowable, Paragraph) and flowable.style.name in {"H1", "H2"}:
            text = flowable.getPlainText()
            self._headings = getattr(self, "_headings", 0) + 1
            key = f"h{self._headings}"
            self.canv.bookmarkPage(key)
            level = 0 if flowable.style.name == "H1" else 1
            self.canv.addOutlineEntry(text, key, level=level, closed=level == 1)


def _numbered_canvas(document: PatternDocument) -> type[Canvas]:
    lang = document.language

    class NumberedCanvas(Canvas):  # type: ignore[misc]
        """Dos pasadas para poder escribir "Pagina 3 de 12"."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._pages: list[dict[str, Any]] = []

        def showPage(self) -> None:
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self) -> None:
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                if self._pageNumber > 1:
                    self._decorate(total)
                super().showPage()
            super().save()

        def _decorate(self, total: int) -> None:
            width, height = self._pagesize
            self.saveState()
            self.setStrokeColor(_RULE)
            self.setLineWidth(0.5)
            self.line(18 * mm, height - 13 * mm, width - 18 * mm, height - 13 * mm)
            self.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
            self.setFont("Helvetica", 8)
            self.setFillColor(_SOFT)
            self.drawString(18 * mm, height - 11 * mm, f"{document.title} · Tejedora")
            self.drawRightString(width - 18 * mm, height - 11 * mm, document.subtitle)
            self.drawString(18 * mm, 9 * mm, t("doc.copyright", lang, year=document.date[:4]))
            self.drawRightString(
                width - 18 * mm, 9 * mm, t("doc.page", lang, n=self._pageNumber, total=total)
            )
            self.restoreState()

    return NumberedCanvas


def _photo(data: bytes, max_w: float, max_h: float) -> Flowable | None:
    """La foto de la persona en la portada, como en los patrones impresos."""
    try:
        image = Image(BytesIO(data))
    except Exception:  # una foto ilegible no impide el PDF
        return None
    scale = min(max_w / image.imageWidth, max_h / image.imageHeight)
    image.drawWidth, image.drawHeight = image.imageWidth * scale, image.imageHeight * scale
    return image


def render_document_pdf(
    document: PatternDocument, *, paper: Paper = "A4", print_mode: bool = False, photo: bytes | None = None
) -> bytes:
    lang = document.language
    buffer = BytesIO()
    pagesize = LETTER if paper == "Letter" else A4
    doc = _Doc(
        buffer,
        pagesize=pagesize,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=document.title,
        author="Tejedora",
        subject=document.subtitle,
        keywords=["tejido", "patron", *document.sizes],
        creator="Tejedora",
        lang=lang,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame])])
    styles = _styles(print_mode)
    width = doc.width
    story: list[Flowable] = []

    # 1. Portada: titulo, datos y el esquema como ilustracion.
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph(_esc(document.title), styles["cover_title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(_esc(document.subtitle), styles["cover_sub"]))
    story.append(Paragraph("Tejedora", styles["cover_sub"]))
    story.append(Spacer(1, 1 * cm))
    multi = len(document.sizes) > 1
    picture = _photo(photo, width * 0.7, doc.height * 0.38) if photo else None
    if picture is not None:
        story.append(picture)
        story.append(Spacer(1, 4))
        story.append(Paragraph(_esc(t("doc.cover_photo", lang)), styles["cover_sub"]))
        story.append(Spacer(1, 0.6 * cm))
    cover = _drawing(
        document.schematic,
        lang,
        width,
        doc.height * (0.3 if picture is not None else 0.45 if print_mode else 0.6),
        letters_only=multi,
    )
    if cover is not None:
        story.append(cover)
    story.append(PageBreak())

    highlight = document.highlight
    section: list[Flowable] = []

    def flush() -> None:
        nonlocal section
        if section:
            story.append(KeepTogether(section[:2]))
            story.extend(section[2:])
            section = []

    def add(flowable: Flowable) -> None:
        (section if section else story).append(flowable)

    for block in document.blocks:
        kind = block.kind
        if kind is BlockKind.PAGE_BREAK:
            flush()
            story.append(PageBreak())
        elif kind is BlockKind.DOC_HEADING:
            flush()
            story.append(Paragraph(_esc(block.text), styles["h1"]))
        elif kind is BlockKind.SECTION_HEADING:
            flush()
            section = [Paragraph(_esc(block.text), styles["h2"])]
        elif kind is BlockKind.TABLE:
            flush()
            header = len(block.rows) > 1 and len(block.rows[0]) > 2
            column = highlight + 1 if header and highlight is not None else None
            table = _table(block.rows, width, styles, header=header, highlight_col=column, print_mode=print_mode)
            heading = story.pop() if story and isinstance(story[-1], Paragraph) and story[-1].style.name == "H1" else None
            story.append(KeepTogether([heading, table] if heading is not None else [table]))
            story.append(Spacer(1, 4))
        elif kind is BlockKind.SCHEMATIC:
            flush()
            drawing = _drawing(document.schematic, lang, width, doc.height * 0.7, letters_only=multi)
            if drawing is not None:
                heading = story.pop() if story and isinstance(story[-1], Paragraph) and story[-1].style.name == "H1" else None
                story.append(KeepTogether([heading, drawing] if heading is not None else [drawing]))
        elif kind is BlockKind.CHART:
            flush()
            chart = document.charts[int(block.text)]
            svg = render_stitch_chart_svg(chart, repeats=2, lang=lang, in_the_round=True)
            drawing = _svg_drawing(svg, width * 0.8, doc.height * 0.5)
            if drawing is not None:
                heading = story.pop() if story and isinstance(story[-1], Paragraph) and story[-1].style.name == "H1" else None
                story.append(KeepTogether([heading, drawing] if heading is not None else [drawing]))
        elif kind in {BlockKind.STEP, BlockKind.REPEAT}:
            add(Paragraph("• " + _highlight(block.text, highlight, document.sizes, lang), styles["step"]))
        elif kind is BlockKind.WARNING:
            add(Paragraph("• " + _esc(block.text), styles["note"]))
        elif kind is BlockKind.MEASURE:
            add(Paragraph(f"<b>{_esc(block.label or '')}:</b> {_esc(block.text)}", styles["body"]))
        elif kind is BlockKind.GLOSSARY:
            add(Paragraph(f"<b>{_esc(block.label or '')}</b> = {_esc(block.value or '')}", styles["body"]))
        elif kind in {BlockKind.LINE, BlockKind.SUBTITLE}:
            add(Paragraph(_highlight(block.text, highlight, document.sizes, lang), styles["body"]))
    flush()

    doc.build(story, canvasmaker=_numbered_canvas(document))
    return buffer.getvalue()


def render_pattern_pdf(
    pattern: Pattern,
    *,
    lang: str | None = None,
    paper: Paper = "A4",
    print_mode: bool = False,
    all_sizes: bool = True,
    photo: bytes | None = None,
) -> bytes:
    """PDF de un patron. Las prendas incluyen todos los talles verificados,
    con el talle del patron resaltado; si no se pueden regenerar, solo el suyo.
    """
    from engine.garments import GarmentError, generate_size_set

    patterns = [pattern]
    if all_sizes:
        try:
            patterns = generate_size_set(pattern.spec, pattern.params)
        except GarmentError:
            patterns = [pattern]
        if pattern.meta.size not in {p.meta.size for p in patterns}:
            patterns = [pattern]
        # Lo que se aproximo al rutear la foto (ver engine/garments/routing.py)
        # no sale de pattern.spec: se conserva al regenerar los talles.
        carried = [w for w in pattern.warnings if w.code.startswith("approx_")]
        patterns = [
            replace(p, warnings=(*p.warnings, *(w for w in carried if w not in p.warnings)))
            for p in patterns
        ]
    document = build_document(patterns, highlight=pattern.meta.size, lang=lang)
    return render_document_pdf(document, paper=paper, print_mode=print_mode, photo=photo)
