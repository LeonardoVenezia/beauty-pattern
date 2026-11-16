"""Texto determinista del patron a partir de los bloques.

Siempre existe como respaldo del redactor de IA: no agrega ni cambia numeros.
Los patrones se escriben con abreviaturas y un glosario, como los patrones
comerciales; el nivel ya no cambia el vocabulario.
"""

from __future__ import annotations

from engine.blocks import Block, BlockKind, build_pattern_blocks
from engine.colorwork import chart_text_lines
from engine.document import PatternDocument
from engine.ir import Pattern


def render_blocks_text(blocks: tuple[Block, ...]) -> str:
    lines: list[str] = []
    for block in blocks:
        if block.kind in {BlockKind.DOC_HEADING, BlockKind.SECTION_HEADING}:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(block.text)
        elif block.kind is BlockKind.MEASURE:
            lines.append(f"{block.label}: {block.text}")
        elif block.kind is BlockKind.GLOSSARY:
            lines.append(f"{block.label} = {block.value}")
        elif block.kind is BlockKind.WARNING:
            lines.append(f"- {block.text}")
        else:
            lines.append(block.text)
    return "\n".join(lines)


def render_pattern_text(
    pattern: Pattern,
    *,
    lang: str | None = None,
    level: str | None = None,
) -> str:
    return render_blocks_text(build_pattern_blocks(pattern, lang=lang))


def render_document_text(document: PatternDocument) -> str:
    """Documento completo (todas las secciones y talles) en texto plano."""
    lines = [document.title, document.subtitle, ""]
    for block in document.blocks:
        if block.kind is BlockKind.TABLE:
            lines.extend(" | ".join(row) for row in block.rows)
        elif block.kind is BlockKind.SCHEMATIC or block.kind is BlockKind.PAGE_BREAK:
            continue
        elif block.kind is BlockKind.COLORWORK_CHART:
            lines.extend(chart_text_lines(document.colorwork_charts[int(block.text)], document.language))
        else:
            lines.append(render_blocks_text((block,)))
    return "\n".join(lines)
