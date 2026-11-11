from __future__ import annotations

from itertools import product

import pytest

from engine.garments import ImpossibleProportionsError, generate
from engine.simulator import simulate
from engine.sizes import BODY_SIZES
from engine.spec import (
    BodyLength,
    Category,
    Construction,
    Fit,
    GarmentSpec,
    PatternParams,
    SleeveLength,
    Technique,
    YarnWeight,
)
from engine.text import render_pattern_text
from render.pdf import render_pattern_pdf
from render.schematic import render_schematic_svg


def set_in_spec(**updates) -> GarmentSpec:
    base = GarmentSpec(
        categoria=Category.PULLOVER,
        tecnica=Technique.NEEDLES,
        construccion=Construction.SET_IN_SLEEVE,
    )
    return base.model_copy(update=updates)


def test_set_in_golden_size_m() -> None:
    pattern = generate(set_in_spec(), PatternParams(talla="M"))
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]
    assert pattern.meta.family == "set_in"
    counts = {
        section.id: (section.start_stitches, section.end_stitches)
        for section in pattern.sections
    }
    # Talle M, DK 22 x 30: 112 pts por pieza (100 cm de contorno), sisa hasta
    # el ancho de espalda de la tabla (40 cm = 88 pts), copa que termina en
    # 24 pts. Antes la sisa bajaba a 48 pts (forma de raglan, sin hombros).
    assert counts == {
        "back": (0, 88),
        "front": (0, 88),
        "cuff_left": (0, 40),
        "sleeve_left": (40, 24),
        "cuff_right": (0, 40),
        "sleeve_right": (40, 24),
        "neck_band": (0, 80),
    }
    measures = {m.key: m.value_cm for m in pattern.measurements}
    assert measures["cross_back"] == pytest.approx(40.0, abs=1.0)
    assert measures["armhole"] == pytest.approx(21.0, abs=1.0)


@pytest.mark.parametrize(
    ("size", "weight", "fit"),
    list(product(BODY_SIZES, YarnWeight, Fit)),
)
def test_set_in_combinations_simulate(
    size: str, weight: YarnWeight, fit: Fit
) -> None:
    pattern = generate(
        set_in_spec(ajuste=fit),
        PatternParams(talla=size, peso_hilo=weight),
    )
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]


@pytest.mark.parametrize(
    ("body_length", "sleeve_length"),
    [
        (BodyLength.CROPPED, SleeveLength.SHORT),
        (BodyLength.HIP, SleeveLength.THREE_QUARTER),
        (BodyLength.TUNIC, SleeveLength.LONG),
        (BodyLength.LONG, SleeveLength.LONG),
    ],
)
def test_set_in_variants_simulate(
    body_length: BodyLength, sleeve_length: SleeveLength
) -> None:
    pattern = generate(
        set_in_spec(largo_cuerpo=body_length, largo_manga=sleeve_length),
        PatternParams(talla="M"),
    )
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]


def test_set_in_sleeveless_is_rejected() -> None:
    with pytest.raises(ImpossibleProportionsError):
        generate(
            set_in_spec(largo_manga=SleeveLength.SLEEVELESS),
            PatternParams(talla="M"),
        )


def test_set_in_text_svg_and_pdf() -> None:
    pattern = generate(set_in_spec(), PatternParams(talla="M"))
    text = render_pattern_text(pattern, lang="es")
    assert "Montar" in text
    assert "Copa de manga" in text
    svg = render_schematic_svg(pattern)
    assert "<svg" in svg
    pdf = render_pattern_pdf(pattern)
    assert pdf.startswith(b"%PDF")
