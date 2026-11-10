from __future__ import annotations

import xml.etree.ElementTree as ET
from itertools import product

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from engine.garments import (
    ImpossibleProportionsError,
    UnsupportedGarmentError,
    generate,
)
from engine.gauge import Gauge
from engine.ir import Pattern
from engine.simulator import simulate
from engine.sizes import BODY_SIZES
from engine.spec import (
    BodyLength,
    Category,
    Construction,
    Fit,
    GarmentSpec,
    Neckline,
    PatternParams,
    SleeveLength,
    Technique,
    YarnWeight,
)
from engine.text import render_pattern_text
from render.pdf import render_pattern_pdf
from render.schematic import render_raglan_schematic_svg


def base_spec(**overrides: object) -> GarmentSpec:
    data: dict[str, object] = {
        "categoria": Category.PULLOVER,
        "tecnica": Technique.NEEDLES,
        "construccion": Construction.RAGLAN_TOP_DOWN,
    }
    data.update(overrides)
    return GarmentSpec(**data)  # type: ignore[arg-type]


def counts(pattern: Pattern) -> dict[str, tuple[int, int]]:
    return {
        section.id: (section.start_stitches, section.end_stitches)
        for section in pattern.sections
    }


def measurement(pattern: Pattern, key: str) -> float:
    for item in pattern.measurements:
        if item.key == key:
            return item.value_cm
    raise KeyError(key)


def test_golden_size_m() -> None:
    pattern = generate(base_spec(), PatternParams(talla="M"))
    assert simulate(pattern).ok
    assert counts(pattern) == {
        "neckband": (80, 80),
        "yoke": (80, 328),
        "body": (200, 220),
        "hem": (220, 220),
        "sleeve_left": (74, 40),
        "cuff_left": (40, 40),
        "sleeve_right": (74, 40),
        "cuff_right": (40, 40),
    }
    assert measurement(pattern, "yoke_depth") == pytest.approx(25.0)
    assert measurement(pattern, "bust") == pytest.approx(100.0)
    assert measurement(pattern, "body_length") == pytest.approx(58.0)
    assert measurement(pattern, "sleeve_length") == pytest.approx(58.0)
    assert pattern.materials.grams is not None
    assert pattern.materials.grams > 100
    assert pattern.materials.needle_mm == pytest.approx(4.0)


@pytest.mark.parametrize(
    ("size", "weight", "fit"),
    list(product(BODY_SIZES, YarnWeight, Fit)),
)
def test_all_sizes_weights_and_fits_simulate(
    size: str, weight: YarnWeight, fit: Fit
) -> None:
    spec = base_spec(ajuste=fit)
    pattern = generate(spec, PatternParams(talla=size, peso_hilo=weight))
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.issues]
    assert pattern.meta.size == size


@pytest.mark.parametrize(
    "neckline",
    [
        Neckline.CREW,
        Neckline.V_NECK,
        Neckline.BOAT,
        Neckline.TURTLENECK,
        Neckline.FUNNEL,
        Neckline.SQUARE,
    ],
)
@pytest.mark.parametrize("body_length", list(BodyLength))
@pytest.mark.parametrize(
    "sleeve_length",
    [SleeveLength.SHORT, SleeveLength.THREE_QUARTER, SleeveLength.LONG],
)
def test_length_and_neckline_variants_simulate(
    neckline: Neckline, body_length: BodyLength, sleeve_length: SleeveLength
) -> None:
    spec = base_spec(
        escote=neckline, largo_cuerpo=body_length, largo_manga=sleeve_length
    )
    pattern = generate(spec, PatternParams(talla="M"))
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.issues]
    expected = {
        BodyLength.CROPPED: 43.0,
        BodyLength.HIP: 58.0,
        BodyLength.TUNIC: 66.0,
        BodyLength.LONG: 73.0,
    }
    assert measurement(pattern, "body_length") == pytest.approx(
        expected[body_length], abs=1.0
    )


def test_sleeveless_is_rejected_clearly() -> None:
    spec = base_spec(largo_manga=SleeveLength.SLEEVELESS)
    with pytest.raises(ImpossibleProportionsError) as error:
        generate(spec, PatternParams(talla="M"))
    assert error.value.key == "error.unsupported_sleeve"


def test_unsupported_garment_is_rejected_clearly() -> None:
    with pytest.raises(UnsupportedGarmentError) as error:
        generate(
            GarmentSpec(categoria=Category.BAG, tecnica=Technique.NEEDLES),
            PatternParams(),
        )
    assert error.value.key == "error.unsupported_garment"


def test_unsupported_technique_is_rejected_clearly() -> None:
    with pytest.raises(UnsupportedGarmentError) as error:
        generate(
            GarmentSpec(categoria=Category.PULLOVER, tecnica=Technique.CROCHET),
            PatternParams(),
        )
    assert error.value.key == "error.unsupported_technique"


def test_custom_measurements_are_used() -> None:
    params = PatternParams(
        talla="M", medidas_cm={"bust": 110.0, "body_length": 65.0}
    )
    pattern = generate(base_spec(), params)
    assert simulate(pattern).ok
    assert measurement(pattern, "bust") == pytest.approx(116.0, abs=2.5)
    assert measurement(pattern, "body_length") == pytest.approx(65.0, abs=1.0)


def test_text_svg_and_pdf_are_generated() -> None:
    pattern = generate(base_spec(), PatternParams(talla="M"))
    text_es = render_pattern_text(pattern)
    text_en = render_pattern_text(pattern, lang="en")
    assert "M" in text_es
    assert "220" in text_es
    assert "Sleeve" in text_en or "sleeve" in text_en
    assert "Canesu" in text_es

    svg = render_raglan_schematic_svg(pattern)
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")

    pdf = render_pattern_pdf(pattern)
    assert pdf.startswith(b"%PDF")


def test_generation_is_deterministic() -> None:
    spec = base_spec(escote=Neckline.V_NECK, largo_manga=SleeveLength.THREE_QUARTER)
    params = PatternParams(talla="L", peso_hilo=YarnWeight.WORSTED)
    first = generate(spec, params)
    second = generate(spec, params)
    assert counts(first) == counts(second)
    assert render_pattern_text(first) == render_pattern_text(second)


@given(
    size=st.sampled_from(list(BODY_SIZES)),
    stitches=st.floats(min_value=8.0, max_value=40.0),
    rows=st.floats(min_value=10.0, max_value=50.0),
    fit=st.sampled_from(list(Fit)),
    body_length=st.sampled_from(list(BodyLength)),
    sleeve_length=st.sampled_from(
        [SleeveLength.SHORT, SleeveLength.THREE_QUARTER, SleeveLength.LONG]
    ),
    neckline=st.sampled_from(
        [Neckline.CREW, Neckline.V_NECK, Neckline.BOAT, Neckline.TURTLENECK]
    ),
)
@settings(
    max_examples=120,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_property_generated_patterns_always_simulate(
    size: str,
    stitches: float,
    rows: float,
    fit: Fit,
    body_length: BodyLength,
    sleeve_length: SleeveLength,
    neckline: Neckline,
) -> None:
    spec = base_spec(
        ajuste=fit,
        largo_cuerpo=body_length,
        largo_manga=sleeve_length,
        escote=neckline,
    )
    params = PatternParams(
        talla=size,
        densidad=Gauge(stitches_per_10cm=stitches, rows_per_10cm=rows),
    )
    try:
        pattern = generate(spec, params)
    except ImpossibleProportionsError as error:
        assert error.key in {"error.impossible_proportions", "error.unsupported_sleeve"}
        return
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.issues]
