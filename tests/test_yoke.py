from __future__ import annotations

from itertools import product

import pytest

from engine.garments import generate
from engine.simulator import simulate
from engine.sizes import BODY_SIZES
from engine.spec import (
    BodyLength,
    Category,
    Colorwork,
    ColorworkType,
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
from render.schematic import render_schematic_svg


def yoke_spec(**updates) -> GarmentSpec:
    base = GarmentSpec(
        categoria=Category.PULLOVER,
        tecnica=Technique.CIRCULAR,
        construccion=Construction.YOKE,
    )
    return base.model_copy(update=updates)


def test_yoke_golden_size_m() -> None:
    pattern = generate(yoke_spec(), PatternParams(talla="M"))
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]
    assert pattern.meta.family == "yoke"
    counts = {
        section.id: (section.start_stitches, section.end_stitches)
        for section in pattern.sections
    }
    assert counts == {
        "neckband": (80, 80),
        "yoke": (80, 328),
        "body": (200, 220),
        "hem": (220, 220),
        "sleeve_left": (74, 40),
        "cuff_left": (40, 40),
        "sleeve_right": (74, 40),
        "cuff_right": (40, 40),
    }


@pytest.mark.parametrize(
    ("size", "weight", "fit"),
    list(product(BODY_SIZES, YarnWeight, Fit)),
)
def test_yoke_combinations_simulate(
    size: str, weight: YarnWeight, fit: Fit
) -> None:
    pattern = generate(
        yoke_spec(ajuste=fit),
        PatternParams(talla=size, peso_hilo=weight),
    )
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]


@pytest.mark.parametrize(
    ("body_length", "sleeve_length", "neckline"),
    [
        (BodyLength.CROPPED, SleeveLength.LONG, Neckline.CREW),
        (BodyLength.HIP, SleeveLength.SHORT, Neckline.CREW),
        (BodyLength.TUNIC, SleeveLength.THREE_QUARTER, Neckline.V_NECK),
        (BodyLength.LONG, SleeveLength.LONG, Neckline.BOAT),
        (BodyLength.HIP, SleeveLength.LONG, Neckline.TURTLENECK),
    ],
)
def test_yoke_variants_simulate(
    body_length: BodyLength,
    sleeve_length: SleeveLength,
    neckline: Neckline,
) -> None:
    pattern = generate(
        yoke_spec(
            largo_cuerpo=body_length,
            largo_manga=sleeve_length,
            escote=neckline,
        ),
        PatternParams(talla="M"),
    )
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]


def test_yoke_sleeveless_goes_to_set_in() -> None:
    pattern = generate(yoke_spec(largo_manga=SleeveLength.SLEEVELESS), PatternParams(talla="M"))
    assert pattern.meta.family == "set_in" and simulate(pattern).ok


def test_yoke_fair_isle_is_charted() -> None:
    pattern = generate(
        yoke_spec(
            colorwork=Colorwork(
                tipo=ColorworkType.FAIR_ISLE,
                paleta=["#ffffff", "#222222"],
            )
        ),
        PatternParams(talla="M"),
    )
    assert simulate(pattern).ok
    codes = {w.code for w in pattern.warnings}
    assert "colorwork_charted" in codes
    assert "colorwork_not_charted" not in codes
    assert pattern.materials.colors == ("#ffffff", "#222222")


def test_yoke_intarsia_is_declared_not_charted() -> None:
    pattern = generate(
        yoke_spec(colorwork=Colorwork(tipo=ColorworkType.INTARSIA, paleta=["#ffffff", "#222222"])),
        PatternParams(talla="M"),
    )
    assert simulate(pattern).ok
    assert any(w.code == "colorwork_not_charted" for w in pattern.warnings)


def test_yoke_text_svg_and_pdf() -> None:
    pattern = generate(yoke_spec(), PatternParams(talla="M"))
    text = render_pattern_text(pattern, lang="es")
    assert "Canesú" in text
    svg = render_schematic_svg(pattern)
    assert "<svg" in svg
    assert "Pullover con canesú circular" in svg
    pdf = render_pattern_pdf(pattern)
    assert pdf.startswith(b"%PDF")


def test_yoke_multisize_text_reads_like_a_published_pattern() -> None:
    """Pocas vueltas de aumento (siempre la misma cantidad) con vueltas lisas
    entre medio: el texto multitalle no se parte en lineas "Solo talles"."""
    from engine.document import build_document
    from engine.text import render_document_text

    patterns = [generate(yoke_spec(), PatternParams(talla=size)) for size in BODY_SIZES]
    text = render_document_text(build_document(patterns))
    yoke = text[text.index("Canesú\n") : text.index("Cuerpo\n")]
    assert "Solo talles" not in yoke
    assert yoke.count("Vuelta de aumentos repartidos") == 6
    assert "raglán" not in yoke
