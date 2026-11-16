"""Criterios de aceptacion de la especificacion de patron de mercado."""

from __future__ import annotations

import re

import pytest

from engine.blocks import BlockKind
from engine.document import build_document, cyc_level
from engine.garments import generate_size_set
from engine.i18n import t
from engine.spec import Category, Construction, GarmentSpec, PatternParams, Technique
from render.pdf import render_document_pdf

SWEATER = GarmentSpec(
    categoria=Category.PULLOVER, tecnica=Technique.CIRCULAR, construccion=Construction.RAGLAN_TOP_DOWN
)
SHAWL = GarmentSpec(categoria=Category.SHAWL, tecnica=Technique.NEEDLES)
AMIGURUMI = GarmentSpec(categoria=Category.AMIGURUMI, tecnica=Technique.CROCHET)
GRANNY = GarmentSpec(categoria=Category.GRANNY_SQUARE, tecnica=Technique.CROCHET)
EXAMPLES = [SWEATER, SHAWL, AMIGURUMI, GRANNY]

REQUIRED = [
    "pattern.schematic",
    "doc.description",
    "doc.technical",
    "doc.materials",
    "doc.gauge",
    "pattern.abbreviations",
    "pattern.notes",
    "pattern.instructions",
    "pattern.finished",
]


def _doc(spec: GarmentSpec):  # type: ignore[no-untyped-def]
    return build_document(generate_size_set(spec, PatternParams()), highlight="M")


@pytest.mark.parametrize("spec", EXAMPLES, ids=lambda s: s.categoria.value)
def test_sections_present_in_order(spec: GarmentSpec) -> None:
    headings = [b.text for b in _doc(spec).blocks if b.kind is BlockKind.DOC_HEADING]
    expected = [t(key, "es") for key in REQUIRED]
    positions = [headings.index(title) for title in expected]
    assert positions == sorted(positions)


def test_sized_garment_has_size_table_with_all_sizes() -> None:
    document = _doc(SWEATER)
    assert t("doc.size_table", "es") in [b.text for b in document.blocks]
    table = next(b for b in document.blocks if b.kind is BlockKind.TABLE and len(b.rows[0]) > 2)
    assert table.rows[0][1:] == document.sizes
    assert len(document.sizes) >= 6


@pytest.mark.parametrize("spec", EXAMPLES, ids=lambda s: s.categoria.value)
def test_glossary_lists_only_used_abbreviations(spec: GarmentSpec) -> None:
    document = _doc(spec)
    blocks = list(document.blocks)
    start = next(i for i, b in enumerate(blocks) if b.text == t("pattern.instructions", "es"))
    text = " ".join(b.text for b in blocks[start:] if b.kind is not BlockKind.TABLE).lower()
    glossary = next(
        b for i, b in enumerate(blocks)
        if b.kind is BlockKind.TABLE and blocks[i - 1].text == t("pattern.abbreviations", "es")
    )
    for label, _ in glossary.rows[1:]:
        assert re.search(rf"(?<!\w){re.escape(label.lower())}(?!\w)", text), label


def test_levels_follow_cyc() -> None:
    assert cyc_level(generate_size_set(SWEATER, PatternParams())) == 3
    assert cyc_level(generate_size_set(GRANNY, PatternParams())) == 2


@pytest.mark.parametrize("paper", ["A4", "Letter"])
def test_pdf_has_outline_pages_and_metadata(paper: str) -> None:
    pdf = render_document_pdf(_doc(SWEATER), paper=paper)  # type: ignore[arg-type]
    assert pdf.startswith(b"%PDF")
    assert b"/Outlines" in pdf
    assert b"Tejedora" in pdf
    print_pdf = render_document_pdf(_doc(SWEATER), print_mode=True)
    assert print_pdf.startswith(b"%PDF")


_KEY_LEAK = re.compile(
    r"\b(?:pattern|doc|schematic|warning|measure|title|section|desc|op|join|notion|stitch|glossary)\.[a-z_.]+"
)


@pytest.mark.parametrize("category", list(Category), ids=lambda c: c.value)
@pytest.mark.parametrize("technique", list(Technique), ids=lambda t: t.value)
def test_every_family_renders_without_raw_keys(category: Category, technique: Technique) -> None:
    """Cualquier combinacion de la IA da un patron (directo o aproximado)."""
    from engine.text import render_document_text

    patterns = generate_size_set(GarmentSpec(categoria=category, tecnica=technique), PatternParams())
    document = build_document(patterns, highlight="M")
    assert not _KEY_LEAK.findall(render_document_text(document))
    assert render_document_pdf(document).startswith(b"%PDF")
