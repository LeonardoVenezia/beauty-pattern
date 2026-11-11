from __future__ import annotations

from itertools import pairwise, product

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


def spec_for(category: Category, construction: Construction | None = None) -> GarmentSpec:
    return GarmentSpec(
        categoria=category,
        tecnica=Technique.NEEDLES,
        construccion=construction,
    )


def counts(pattern) -> dict[str, tuple[int, int]]:
    return {
        section.id: (section.start_stitches, section.end_stitches)
        for section in pattern.sections
    }


def test_drop_shoulder_golden_size_m() -> None:
    pattern = generate(
        spec_for(Category.PULLOVER, Construction.DROP_SHOULDER),
        PatternParams(talla="M"),
    )
    assert simulate(pattern).ok
    assert pattern.meta.family == "drop_shoulder"
    assert counts(pattern) == {
        "back": (0, 110),
        "front": (0, 110),
        "sleeve_left": (0, 76),
        "cuff_left": (0, 76),
        "sleeve_right": (0, 76),
        "cuff_right": (0, 76),
        "neckband": (0, 88),
    }


def test_cardigan_has_button_bands_and_seams() -> None:
    pattern = generate(
        spec_for(Category.CARDIGAN, Construction.DROP_SHOULDER),
        PatternParams(talla="M"),
    )
    assert simulate(pattern).ok
    assert pattern.meta.family == "cardigan"
    assert "button_band_left" in counts(pattern)
    assert "button_band_right" in counts(pattern)
    assert any(w.code == "no_buttonholes" for w in pattern.warnings)


def test_vest_has_no_sleeves() -> None:
    pattern = generate(spec_for(Category.VEST), PatternParams(talla="L"))
    assert simulate(pattern).ok
    assert pattern.meta.family == "vest"
    assert not any(section.id.startswith("sleeve_") for section in pattern.sections)
    assert any(w.code == "vest_armhole" for w in pattern.warnings)


@pytest.mark.parametrize(
    ("category", "construction"),
    [
        (Category.PULLOVER, Construction.DROP_SHOULDER),
        (Category.CARDIGAN, Construction.DROP_SHOULDER),
        (Category.VEST, None),
    ],
)
@pytest.mark.parametrize(
    ("size", "weight", "fit"),
    list(product(BODY_SIZES, YarnWeight, Fit)),
)
def test_flat_combinations_simulate(
    category: Category,
    construction: Construction | None,
    size: str,
    weight: YarnWeight,
    fit: Fit,
) -> None:
    pattern = generate(
        spec_for(category, construction).model_copy(update={"ajuste": fit}),
        PatternParams(talla=size, peso_hilo=weight),
    )
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]


@pytest.mark.parametrize(
    ("body_length", "sleeve_length"),
    [
        (BodyLength.CROPPED, SleeveLength.SHORT),
        (BodyLength.TUNIC, SleeveLength.THREE_QUARTER),
        (BodyLength.LONG, SleeveLength.LONG),
    ],
)
def test_drop_shoulder_variants(
    body_length: BodyLength, sleeve_length: SleeveLength
) -> None:
    pattern = generate(
        spec_for(Category.PULLOVER, Construction.DROP_SHOULDER).model_copy(
            update={"largo_cuerpo": body_length, "largo_manga": sleeve_length}
        ),
        PatternParams(talla="M"),
    )
    assert simulate(pattern).ok


def test_flat_sleeveless_pullover_is_rejected() -> None:
    spec = spec_for(Category.PULLOVER, Construction.DROP_SHOULDER).model_copy(
        update={"largo_manga": SleeveLength.SLEEVELESS}
    )
    with pytest.raises(ImpossibleProportionsError):
        generate(spec, PatternParams(talla="M"))


def test_flat_text_svg_and_pdf() -> None:
    pattern = generate(
        spec_for(Category.CARDIGAN, Construction.DROP_SHOULDER),
        PatternParams(talla="M"),
    )
    text = render_pattern_text(pattern, lang="es")
    assert "Montar" in text
    assert "Tapa de botones" in text
    svg = render_schematic_svg(pattern)
    assert "<svg" in svg
    # El esquema incluye cotas con valor en cm.
    assert "cm" in svg
    assert "<polygon" in svg
    pdf = render_pattern_pdf(pattern)
    assert pdf.startswith(b"%PDF")


@pytest.mark.parametrize(
    "spec",
    [
        GarmentSpec(categoria=Category.PULLOVER, tecnica=Technique.NEEDLES, construccion=Construction.DROP_SHOULDER),
        GarmentSpec(categoria=Category.CARDIGAN, tecnica=Technique.NEEDLES),
        GarmentSpec(categoria=Category.VEST, tecnica=Technique.NEEDLES),
        GarmentSpec(categoria=Category.PULLOVER, tecnica=Technique.NEEDLES, construccion=Construction.SET_IN_SLEEVE),
    ],
    ids=["drop_shoulder", "cardigan", "vest", "set_in"],
)
def test_flat_stockinette_purls_wrong_side_rows(spec: GarmentSpec) -> None:
    """Regresion: todas las hileras al derecho en plano es santa clara, no jersey."""
    from engine.ir import Op
    from engine.stitches.kinds import StitchKind

    pattern = generate(spec, PatternParams(talla="M"))
    for section in pattern.sections:
        if section.mode != "flat" or section.id.startswith(("cuff", "neck", "button")):
            continue
        start = next(
            (i for i, step in enumerate(section.steps) if step.note_key == "pattern.note.flat_panel"), 0
        )
        plain = [
            step.items[0].kind
            for step in section.steps[start:]
            if len(step.items) == 1
            and isinstance(step.items[0], Op)
            and step.items[0].kind in {StitchKind.KNIT, StitchKind.PURL}
        ]
        assert StitchKind.PURL in plain, section.id
        for a, b in pairwise(plain):
            assert not (a is b is StitchKind.KNIT), section.id
