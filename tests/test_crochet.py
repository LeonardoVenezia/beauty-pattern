from __future__ import annotations

from itertools import product

import pytest

from engine.garments import ImpossibleProportionsError, generate
from engine.simulator import simulate
from engine.spec import (
    Category,
    GarmentSpec,
    PatternParams,
    Shape,
    StitchPatternName,
    Technique,
    YarnWeight,
)
from engine.text import render_pattern_text
from render.pdf import render_pattern_pdf
from render.schematic import render_schematic_svg


def amigurumi(shape: Shape | None = None) -> GarmentSpec:
    return GarmentSpec(
        categoria=Category.AMIGURUMI,
        tecnica=Technique.CROCHET,
        forma=shape,
    )


@pytest.mark.parametrize(
    ("shape", "weight"),
    list(
        product(
            (None, Shape.BOXY, Shape.A_LINE),
            YarnWeight,
        )
    ),
)
def test_amigurumi_shapes_simulate(shape: Shape | None, weight: YarnWeight) -> None:
    try:
        pattern = generate(amigurumi(shape), PatternParams(peso_hilo=weight))
    except ImpossibleProportionsError:
        # Hilo muy grueso para 8 cm: debe fallar claro, nunca entregar mal.
        assert weight is YarnWeight.SUPER_BULKY
        return
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]
    assert pattern.sections[0].steps[0].expanded_ops()[0].kind.value == "magic_ring"


def test_super_bulky_small_amigurumi_is_rejected() -> None:
    with pytest.raises(ImpossibleProportionsError):
        generate(amigurumi(), PatternParams(peso_hilo=YarnWeight.SUPER_BULKY))


def test_crochet_uses_crochet_gauge_not_knitting() -> None:
    """Regresion: el pa de DK no puede usar 30 vueltas/10 cm de dos agujas."""
    spec = GarmentSpec(
        categoria=Category.OTHER,
        tecnica=Technique.CROCHET,
        punto_base=StitchPatternName.CROCHET_DC,
    )
    pattern = generate(spec, PatternParams(dimensiones_cm={"width": 20, "length": 20}))
    assert simulate(pattern).ok
    assert pattern.params.densidad is not None
    assert pattern.params.densidad.rows_per_10cm < 10
    rows = len(pattern.sections[0].steps)
    assert rows < 20


def test_sphere_closes_and_has_measurements() -> None:
    pattern = generate(amigurumi(), PatternParams())
    assert simulate(pattern).ok
    assert pattern.sections[0].end_stitches == 6
    measurements = {m.key: m.value_cm for m in pattern.measurements}
    assert measurements["diameter"] == pytest.approx(8.0, abs=1.5)
    assert measurements["height"] == pytest.approx(8.0, abs=1.5)


def test_custom_amigurumi_dimensions() -> None:
    pattern = generate(
        amigurumi(),
        PatternParams(dimensiones_cm={"diameter": 10.0, "height": 12.0}),
    )
    assert simulate(pattern).ok
    measurements = {m.key: m.value_cm for m in pattern.measurements}
    assert measurements["diameter"] == pytest.approx(10.0, abs=1.5)
    assert measurements["height"] == pytest.approx(12.0, abs=1.5)


def test_granny_square_is_classic_and_declares_scope() -> None:
    pattern = generate(
        GarmentSpec(categoria=Category.BLANKET, tecnica=Technique.CROCHET),
        PatternParams(dimensiones_cm={"size": 20.0}),
    )
    assert simulate(pattern).ok
    assert pattern.meta.family == "granny_square"
    assert any(w.code == "granny_classic" for w in pattern.warnings)
    assert pattern.sections[0].steps[0].expanded_ops()[0].kind.value == "granny_start"


def test_granny_square_category_is_supported() -> None:
    pattern = generate(
        GarmentSpec(categoria=Category.GRANNY_SQUARE, tecnica=Technique.CROCHET),
        PatternParams(dimensiones_cm={"size": 20.0}),
    )
    assert simulate(pattern).ok
    assert pattern.meta.family == "granny_square"
    measurements = {m.key: m.value_cm for m in pattern.measurements}
    assert measurements["width"] == pytest.approx(20.0, abs=1.5)
    assert measurements["length"] == pytest.approx(20.0, abs=1.5)
    svg = render_schematic_svg(pattern)
    assert "<svg" in svg
    assert "20 cm" in svg
    assert svg.count("<rect") >= 8  # una franja por vuelta
    assert render_pattern_pdf(pattern).startswith(b"%PDF")


@pytest.mark.parametrize(
    ("category", "family"),
    [(Category.BAG, "crochet_bag"), (Category.OTHER, "crochet_flat_piece")],
)
def test_crochet_bag_and_flat_piece_simulate(
    category: Category, family: str
) -> None:
    pattern = generate(
        GarmentSpec(categoria=category, tecnica=Technique.CROCHET),
        PatternParams(dimensiones_cm={"width": 28.0, "length": 32.0}),
    )
    assert simulate(pattern).ok
    assert pattern.meta.family == family
    measurements = {m.key: m.value_cm for m in pattern.measurements}
    assert measurements["width"] == pytest.approx(28.0, abs=1.5)
    assert measurements["length"] == pytest.approx(32.0, abs=1.5)


def test_crochet_scarf_simulates() -> None:
    pattern = generate(
        GarmentSpec(categoria=Category.SCARF, tecnica=Technique.CROCHET),
        PatternParams(dimensiones_cm={"width": 30.0, "length": 150.0}),
    )
    assert simulate(pattern).ok
    assert pattern.meta.family == "crochet_scarf"


@pytest.mark.parametrize(
    "spec",
    [
        amigurumi(),
        GarmentSpec(categoria=Category.BLANKET, tecnica=Technique.CROCHET),
        GarmentSpec(categoria=Category.SCARF, tecnica=Technique.CROCHET),
        GarmentSpec(categoria=Category.BAG, tecnica=Technique.CROCHET),
        GarmentSpec(categoria=Category.OTHER, tecnica=Technique.CROCHET),
    ],
)
def test_crochet_text_svg_and_pdf(spec: GarmentSpec) -> None:
    pattern = generate(spec, PatternParams())
    text = render_pattern_text(pattern, lang="es")
    assert "anillo mágico" in text or "cadenas" in text
    assert "Rematar" in text
    assert "<svg" in render_schematic_svg(pattern)
    assert render_pattern_pdf(pattern).startswith(b"%PDF")


@pytest.mark.parametrize("weight", list(YarnWeight))
@pytest.mark.parametrize("size", [8.0, 15.0, 20.0, 35.0, 90.0])
def test_granny_square_closes_in_rounds(weight: YarnWeight, size: float) -> None:
    from engine.garments.crochet import granny_round_stitches

    spec = GarmentSpec(categoria=Category.GRANNY_SQUARE, tecnica=Technique.CROCHET)
    pattern = generate(spec, PatternParams(peso_hilo=weight, dimensiones_cm={"size": size}))
    assert simulate(pattern).ok
    section = pattern.sections[0]
    assert section.mode == "round"
    for number, step in enumerate(section.steps, start=1):
        assert step.stitch_count_end == granny_round_stitches(number)
    width = {m.key: m.value_cm for m in pattern.measurements}["width"]
    assert width == pytest.approx(size, abs=max(2.5, size * 0.1))


def test_granny_square_text_is_standard() -> None:
    spec = GarmentSpec(categoria=Category.GRANNY_SQUARE, tecnica=Technique.CROCHET)
    text = render_pattern_text(generate(spec, PatternParams(dimensiones_cm={"size": 15})))
    assert "Vuelta 1: *(3 pa, 2 cad) en el anillo; rep desde * 3 veces más [4 grupos" in text
    assert "esp de esquina" in text
    assert "Hileras" not in text
