"""Hexagonos (6 esquinas, lados iguales) y estilos de granny square."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from engine.garments import ImpossibleProportionsError, generate
from engine.garments.crochet import granny_round_stitches
from engine.garments.routing import route
from engine.simulator import simulate
from engine.spec import (
    Category,
    Colorwork,
    ColorworkType,
    GarmentSpec,
    GrannyStyle,
    MotifBand,
    MotifDesign,
    MotifShape,
    MotifStitch,
    PatternParams,
    Technique,
    YarnWeight,
)
from engine.stitches.kinds import StitchKind
from render.schematic import render_schematic_svg

_HEX = {StitchKind.HEX_CORNER, StitchKind.HEX_CORNER_SC}


def _spec(design: MotifDesign, category: Category = Category.GRANNY_SQUARE) -> GarmentSpec:
    return GarmentSpec(
        categoria=category,
        tecnica=Technique.CROCHET,
        motivo=design,
        colorwork=Colorwork(tipo=ColorworkType.STRIPES, paleta=["crema", "verde", "rosa"]),
    )


def _sides(ops: list[StitchKind], produced: list[int]) -> list[int]:
    corners = [i for i, kind in enumerate(ops) if kind in _HEX]
    ends = [*corners[1:], corners[0] + len(ops)]
    return [sum(produced[k % len(ops)] for k in range(a + 1, b)) for a, b in zip(corners, ends, strict=True)]


def test_single_crochet_hexagon_grows_six_per_round() -> None:
    design = MotifDesign(forma=MotifShape.HEXAGON, simetria=6, bandas=[MotifBand(punto=MotifStitch.SC)], cuadrar_en_banda=0)
    pattern = generate(_spec(design, Category.OTHER), PatternParams(dimensiones_cm={"size": 15}))
    counts = [s.stitch_count_end for s in pattern.sections[0].steps]
    assert counts == [6 * (n + 1) for n in range(len(counts))]
    assert simulate(pattern).ok


@given(
    stitches=st.lists(st.sampled_from(list(MotifStitch)), min_size=1, max_size=4),
    symmetry=st.integers(3, 12),
    size=st.floats(8, 40),
    weight=st.sampled_from([YarnWeight.FINGERING, YarnWeight.DK, YarnWeight.WORSTED, YarnWeight.BULKY]),
)
@settings(max_examples=120, deadline=None)
def test_every_hexagon_round_has_six_equal_sides(
    stitches: list[MotifStitch], symmetry: int, size: float, weight: YarnWeight
) -> None:
    design = MotifDesign(
        forma=MotifShape.HEXAGON,
        simetria=symmetry,
        bandas=[MotifBand(punto=s, color=i % 3) for i, s in enumerate(stitches)],
    )
    try:
        pattern = generate(_spec(design), PatternParams(peso_hilo=weight, dimensiones_cm={"size": size}))
    except ImpossibleProportionsError:  # simetria imposible: rechazo honesto del motor
        return
    report = simulate(pattern)
    assert report.ok, report.errors
    hex_rounds = 0
    for step in pattern.sections[0].steps:
        ops = step.expanded_ops()
        kinds = [op.kind for op in ops]
        if not _HEX & set(kinds):
            assert hex_rounds == 0, "una vuelta redonda despues del hexagono"
            continue
        hex_rounds += 1
        sides = _sides(kinds, [op.produces for op in ops])
        assert len(sides) == 6 and len(set(sides)) == 1, sides
    if len(pattern.sections[0].steps) > 1:
        assert hex_rounds >= 1


def test_hexagon_is_no_longer_approximated() -> None:
    design = MotifDesign(forma=MotifShape.HEXAGON, bandas=[MotifBand(punto=MotifStitch.DC)])
    _, notes = route(_spec(design))
    assert "motif_shape" not in notes


def test_hexagon_drawing_is_a_hexagon() -> None:
    design = MotifDesign(forma=MotifShape.HEXAGON, simetria=6, bandas=[MotifBand(punto=MotifStitch.DC, color=0)])
    pattern = generate(_spec(design), PatternParams())
    svg = render_schematic_svg(pattern)
    assert svg.count("<polygon") >= len(pattern.sections[0].steps) - 1


def test_solid_granny_counts_match_the_classic() -> None:
    design = MotifDesign(forma=MotifShape.SQUARE, bandas=[MotifBand(punto=MotifStitch.DC)], estilo_granny=GrannyStyle.SOLID)
    pattern = generate(_spec(design), PatternParams(dimensiones_cm={"size": 20}))
    assert simulate(pattern).ok
    assert pattern.meta.title_key == "title.granny_solid"
    steps = pattern.sections[0].steps
    assert [s.stitch_count_end for s in steps] == [granny_round_stitches(n) for n in range(1, len(steps) + 1)]
    kinds = {op.kind for s in steps[1:] for op in s.expanded_ops()}
    assert kinds == {StitchKind.DC, StitchKind.CORNER_DC}
    assert "<svg" in render_schematic_svg(pattern)


def test_classic_style_gives_the_classic_granny() -> None:
    design = MotifDesign(forma=MotifShape.SQUARE, bandas=[MotifBand(punto=MotifStitch.DC)], estilo_granny=GrannyStyle.CLASSIC)
    pattern = generate(_spec(design), PatternParams())
    assert pattern.meta.title_key == "title.granny_square"
    assert simulate(pattern).ok


def test_flower_granny_has_petals_and_squares() -> None:
    design = MotifDesign(forma=MotifShape.SQUARE, bandas=[MotifBand(punto=MotifStitch.DC)], estilo_granny=GrannyStyle.FLOWER)
    pattern = generate(_spec(design), PatternParams(dimensiones_cm={"size": 15}))
    assert simulate(pattern).ok
    kinds = {op.kind for s in pattern.sections[0].steps for op in s.expanded_ops()}
    assert StitchKind.PUFF in kinds and StitchKind.SQUARE_TURN in kinds
