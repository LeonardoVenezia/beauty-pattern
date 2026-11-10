from __future__ import annotations

from itertools import product

import pytest

from engine.garments import generate
from engine.simulator import simulate
from engine.spec import (
    Category,
    GarmentSpec,
    PatternParams,
    Shape,
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
    pattern = generate(amigurumi(shape), PatternParams(peso_hilo=weight))
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]
    assert pattern.sections[0].steps[0].expanded_ops()[0].kind.value == "magic_ring"


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


def test_granny_square_is_flat_and_declared_simplified() -> None:
    pattern = generate(
        GarmentSpec(categoria=Category.BLANKET, tecnica=Technique.CROCHET),
        PatternParams(dimensiones_cm={"size": 20.0}),
    )
    assert simulate(pattern).ok
    assert pattern.meta.family == "granny_square"
    assert any(w.code == "granny_simplified" for w in pattern.warnings)
    assert pattern.sections[0].steps[0].expanded_ops()[0].kind.value == "ch"


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
    assert "anillo magico" in text or "cadenas" in text
    assert "Rematar" in text
    assert "<svg" in render_schematic_svg(pattern)
    assert render_pattern_pdf(pattern).startswith(b"%PDF")
