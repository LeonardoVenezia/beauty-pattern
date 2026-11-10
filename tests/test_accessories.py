from __future__ import annotations

from itertools import product

import pytest

from engine.garments import UnsupportedGarmentError, generate
from engine.simulator import simulate
from engine.sizes import BODY_SIZES
from engine.spec import (
    Category,
    GarmentSpec,
    PatternParams,
    Technique,
    YarnWeight,
)
from engine.text import render_pattern_text
from render.pdf import render_pattern_pdf
from render.schematic import render_schematic_svg

ACCESSORIES = [
    Category.HAT,
    Category.SCARF,
    Category.COWL,
    Category.MITTENS,
    Category.SOCKS,
    Category.SHAWL,
    Category.BLANKET,
]


def accessory_spec(category: Category) -> GarmentSpec:
    technique = (
        Technique.CIRCULAR
        if category in {Category.HAT, Category.COWL, Category.SOCKS}
        else Technique.NEEDLES
    )
    return GarmentSpec(categoria=category, tecnica=technique)


@pytest.mark.parametrize("category", ACCESSORIES)
@pytest.mark.parametrize(
    ("size", "weight"), list(product(BODY_SIZES, YarnWeight))
)
def test_accessory_combinations_simulate(
    category: Category, size: str, weight: YarnWeight
) -> None:
    pattern = generate(
        accessory_spec(category), PatternParams(talla=size, peso_hilo=weight)
    )
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]


def test_hat_has_brim_body_and_crown() -> None:
    pattern = generate(
        accessory_spec(Category.HAT), PatternParams(talla="M")
    )
    assert simulate(pattern).ok
    assert pattern.meta.family == "hat"
    assert [section.id for section in pattern.sections] == ["brim", "body", "crown"]
    assert pattern.sections[-1].end_stitches == 4


def test_socks_are_tube_with_declared_heel_limitation() -> None:
    pattern = generate(
        accessory_spec(Category.SOCKS), PatternParams(talla="M")
    )
    assert simulate(pattern).ok
    assert any(w.code == "sock_tube" for w in pattern.warnings)
    assert [section.id for section in pattern.sections] == [
        "cuff",
        "leg",
        "foot",
        "toe",
    ]


def test_mittens_and_rectangular_pieces_are_declared() -> None:
    mittens = generate(
        accessory_spec(Category.MITTENS), PatternParams(talla="M")
    )
    assert simulate(mittens).ok
    assert any(w.code == "mittens_flat" for w in mittens.warnings)
    shawl = generate(accessory_spec(Category.SHAWL), PatternParams(talla="M"))
    assert any(w.code == "shawl_rectangular" for w in shawl.warnings)
    blanket = generate(accessory_spec(Category.BLANKET), PatternParams(talla="M"))
    assert any(w.code == "blanket_panel" for w in blanket.warnings)


def test_accessory_custom_dimensions() -> None:
    pattern = generate(
        accessory_spec(Category.SCARF),
        PatternParams(
            talla="M",
            dimensiones_cm={"width": 30.0, "length": 150.0},
        ),
    )
    assert simulate(pattern).ok
    measurements = {m.key: m.value_cm for m in pattern.measurements}
    assert measurements["width"] == pytest.approx(30.0, abs=1.5)
    assert measurements["length"] == pytest.approx(150.0, abs=1.5)


@pytest.mark.parametrize("category", ACCESSORIES)
def test_accessory_text_svg_and_pdf(category: Category) -> None:
    pattern = generate(accessory_spec(category), PatternParams(talla="M"))
    text = render_pattern_text(pattern, lang="es")
    assert "Montar" in text
    svg = render_schematic_svg(pattern)
    assert "<svg" in svg
    pdf = render_pattern_pdf(pattern)
    assert pdf.startswith(b"%PDF")


def test_unsupported_accessory_is_rejected_clearly() -> None:
    with pytest.raises(UnsupportedGarmentError):
        generate(
            GarmentSpec(categoria=Category.BAG, tecnica=Technique.NEEDLES),
            PatternParams(),
        )
