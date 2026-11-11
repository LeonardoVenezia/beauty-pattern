from __future__ import annotations

from itertools import product

import pytest

from engine.garments import generate
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
    Category.BAG,
    Category.OTHER,
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
    assert [section.id for section in mittens.sections] == ["hand", "thumb"]
    assert any(w.code == "mittens_flat" for w in mittens.warnings)
    text = render_pattern_text(mittens, lang="es")
    assert "Hacé 2 piezas iguales para las manos" in text
    assert "Hacé 2 piezas iguales para los pulgares" in text
    assert text.count("Mano") == 1
    svg = render_schematic_svg(mittens)
    assert "<path" in svg
    assert "Largo del pulgar" in svg
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


def test_bag_and_flat_piece_are_supported() -> None:
    for category, family in (
        (Category.BAG, "bag"),
        (Category.OTHER, "flat_piece"),
    ):
        pattern = generate(
            GarmentSpec(categoria=category, tecnica=Technique.NEEDLES),
            PatternParams(dimensiones_cm={"width": 24.0, "length": 28.0}),
        )
        assert simulate(pattern).ok
        assert pattern.meta.family == family
        measurements = {m.key: m.value_cm for m in pattern.measurements}
        assert measurements["width"] == pytest.approx(24.0, abs=1.5)
        assert measurements["length"] == pytest.approx(28.0, abs=1.5)
        assert "<svg" in render_schematic_svg(pattern)
        assert render_pattern_pdf(pattern).startswith(b"%PDF")


def test_bag_schematic_is_a_technical_drawing() -> None:
    bag = generate(
        GarmentSpec(categoria=Category.BAG, tecnica=Technique.NEEDLES),
        PatternParams(dimensiones_cm={"width": 30.0, "length": 30.0}),
    )
    svg = render_schematic_svg(bag)
    assert "<svg" in svg
    assert 'aria-labelledby="schematic-title schematic-desc"' in svg
    # Cotas y silueta del bolso.
    assert "30.0 cm" in svg
    assert "Asas opcionales (no incluidas)" in svg or "optional_handles" in svg
    assert svg.count("<path") >= 4
    assert "<polygon" in svg  # puntas de flecha de cota


def test_machine_knit_is_translated_to_hand_knitting() -> None:
    pattern = generate(
        GarmentSpec(categoria=Category.SCARF, tecnica=Technique.MACHINE),
        PatternParams(),
    )
    assert pattern.spec.tecnica is Technique.NEEDLES
    assert "approx_machine" in {w.code for w in pattern.warnings}
