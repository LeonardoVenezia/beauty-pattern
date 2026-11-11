"""Capa de diseno: motivos radiales de crochet descriptos por bandas."""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from engine.document import build_document
from engine.garments import generate
from engine.simulator import simulate
from engine.spec import (
    Category,
    Colorwork,
    ColorworkType,
    GarmentSpec,
    MotifBand,
    MotifDesign,
    MotifShape,
    MotifStitch,
    PatternParams,
    Technique,
    YarnWeight,
)
from engine.stitches.kinds import StitchKind
from engine.text import render_document_text
from render.pdf import render_pattern_pdf
from render.schematic import render_schematic_svg


def motif_spec(design: MotifDesign, category: Category = Category.GRANNY_SQUARE) -> GarmentSpec:
    return GarmentSpec(
        categoria=category,
        tecnica=Technique.CROCHET,
        motivo=design,
        colorwork=Colorwork(tipo=ColorworkType.STRIPES, paleta=["crema", "verde", "rosa"]),
    )


MANDALA = MotifDesign(
    forma=MotifShape.SQUARE,
    simetria=8,
    bandas=[
        MotifBand(punto=MotifStitch.DC, color=0),
        MotifBand(punto=MotifStitch.POPCORN, color=1),
        MotifBand(punto=MotifStitch.MESH, color=0, peso=2),
        MotifBand(punto=MotifStitch.DC, color=2),
        MotifBand(punto=MotifStitch.HDC, color=0),
        MotifBand(punto=MotifStitch.DC, color=1),
    ],
)


def test_single_crochet_circle_grows_like_the_classic_flat_circle() -> None:
    design = MotifDesign(simetria=6, bandas=[MotifBand(punto=MotifStitch.SC)])
    pattern = generate(motif_spec(design, Category.OTHER), PatternParams(dimensiones_cm={"size": 12}))
    counts = [s.stitch_count_end for s in pattern.sections[0].steps]
    assert counts[:4] == [6, 12, 18, 24]
    assert simulate(pattern).ok


def test_square_motif_reads_like_a_commercial_pattern() -> None:
    pattern = generate(motif_spec(MANDALA), PatternParams())
    assert pattern.meta.family == "crochet_motif"
    assert simulate(pattern).ok
    steps = pattern.sections[0].steps
    kinds = {op.kind for s in steps for op in s.expanded_ops()}
    assert {StitchKind.POPCORN, StitchKind.SQUARE_TURN, StitchKind.CORNER_DC} <= kinds
    text = render_document_text(build_document([pattern], highlight="M"))
    assert "Banda 2: popcorns" in text and "color B (verde)" in text
    assert "cuadra el motivo" in text
    assert not re.search(r"\b(?:pattern|warning|motif|op|glossary)\.[a-z_.]+", text)
    assert "vueltas desde el centro" in render_schematic_svg(pattern)
    assert render_pattern_pdf(pattern).startswith(b"%PDF")


def test_every_round_repeats_the_same_sequence_around() -> None:
    pattern = generate(motif_spec(MANDALA.model_copy(update={"forma": MotifShape.CIRCLE})), PatternParams())
    for step in pattern.sections[0].steps[1:]:
        assert step.stitch_count_end % MANDALA.simetria == 0


def test_motif_that_cannot_shrink_is_delivered_larger_and_says_so() -> None:
    design = MotifDesign(bandas=[MotifBand(punto=MotifStitch.SC, peso=1) for _ in range(16)])
    pattern = generate(motif_spec(design), PatternParams(peso_hilo=YarnWeight.SUPER_BULKY, dimensiones_cm={"size": 8}))
    assert simulate(pattern).ok
    assert pattern.measurements[0].value_cm > 8
    assert "motif_resized" in {w.code for w in pattern.warnings}


def test_blanket_with_a_motif_gives_one_motif_and_says_so() -> None:
    pattern = generate(motif_spec(MANDALA, Category.BLANKET), PatternParams())
    assert pattern.meta.family == "crochet_motif"
    assert "approx_blanket_motif" in {w.code for w in pattern.warnings}


bands = st.lists(
    st.builds(
        MotifBand,
        punto=st.sampled_from(list(MotifStitch)),
        color=st.one_of(st.none(), st.integers(0, 2)),
        peso=st.integers(1, 4),
    ),
    min_size=1,
    max_size=10,
)


@settings(max_examples=150, deadline=None)
@given(
    shape=st.sampled_from(list(MotifShape)),
    symmetry=st.integers(3, 24),
    bands=bands,
    square_at=st.one_of(st.none(), st.integers(0, 9)),
    size=st.floats(8, 60),
    weight=st.sampled_from([w for w in YarnWeight if w is not YarnWeight.UNKNOWN]),
)
def test_any_described_motif_gives_a_verified_pattern(
    shape: MotifShape, symmetry: int, bands: list[MotifBand], square_at: int | None, size: float, weight: YarnWeight
) -> None:
    design = MotifDesign(forma=shape, simetria=symmetry, bandas=bands, cuadrar_en_banda=square_at)
    pattern = generate(motif_spec(design), PatternParams(peso_hilo=weight, dimensiones_cm={"size": size}))
    assert simulate(pattern).ok
    measured = pattern.measurements[0]
    resized = "motif_resized" in {w.code for w in pattern.warnings}
    assert resized or abs(measured.value_cm - size) <= measured.tolerance_cm
