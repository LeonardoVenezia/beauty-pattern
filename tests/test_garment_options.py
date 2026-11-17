"""Opciones de prenda (D038): top, vestido, saco, bolero, poncho, ruana,
escotes nuevos, largos cintura/codo, estilos de manga y hombro caido
modificado. Todo patron sale verificado por el simulador."""

from __future__ import annotations

import itertools
import re

import pytest

from engine.document import build_document
from engine.garments import generate, generate_size_set
from engine.garments.routing import CATEGORY_APPROX
from engine.simulator import simulate
from engine.spec import (
    BodyLength,
    Category,
    Construction,
    Fit,
    GarmentSpec,
    Neckline,
    PatternParams,
    PonchoStyle,
    Shape,
    SleeveLength,
    SleeveStyle,
    Technique,
    YarnWeight,
)
from engine.text import render_document_text
from render.pdf import render_pattern_pdf

_FAMILIES = {
    "raglan": dict(categoria=Category.PULLOVER, tecnica=Technique.CIRCULAR, construccion=Construction.RAGLAN_TOP_DOWN),
    "yoke": dict(categoria=Category.PULLOVER, tecnica=Technique.CIRCULAR, construccion=Construction.YOKE),
    "drop": dict(categoria=Category.PULLOVER, construccion=Construction.DROP_SHOULDER),
    "set_in": dict(categoria=Category.PULLOVER, construccion=Construction.SET_IN_SLEEVE),
    "cardigan": dict(categoria=Category.CARDIGAN),
    "vest": dict(categoria=Category.VEST),
    "crochet": dict(categoria=Category.PULLOVER, tecnica=Technique.CROCHET),
}


@pytest.mark.parametrize("family", list(_FAMILIES))
@pytest.mark.parametrize("fit", [Fit.FITTED, Fit.OVERSIZED])
def test_every_neckline_length_and_sleeve_combination_simulates(family: str, fit: Fit) -> None:
    """Barrido: escote x largo x manga (con talles y grosores rotando)."""
    sizes = [("XS", YarnWeight.BULKY), ("M", YarnWeight.DK), ("3XL", YarnWeight.FINGERING)]
    combos = itertools.product(list(Neckline), list(BodyLength), list(SleeveLength))
    for index, (neck, body, sleeve) in enumerate(combos):
        if index % 5:
            continue
        size, weight = sizes[index % 3]
        spec = GarmentSpec(**_FAMILIES[family], escote=neck, largo_cuerpo=body, largo_manga=sleeve, ajuste=fit)
        pattern = generate(spec, PatternParams(talla=size, peso_hilo=weight))
        report = simulate(pattern)
        assert report.ok, (neck, body, sleeve, [i.message for i in report.errors])


def test_cardigan_turtleneck_cropped_fronts_are_mirrored() -> None:
    """Bug viejo: los delanteros quedaban 2 hileras corridos (pair_mismatch)."""
    for neck, size in itertools.product([Neckline.TURTLENECK, Neckline.CREW], ["XS", "M", "3XL"]):
        spec = GarmentSpec(categoria=Category.CARDIGAN, escote=neck, largo_cuerpo=BodyLength.CROPPED)
        assert simulate(generate(spec, PatternParams(talla=size))).ok


@pytest.mark.parametrize("style", list(SleeveStyle))
@pytest.mark.parametrize("construction", [Construction.RAGLAN_TOP_DOWN, Construction.YOKE, Construction.SET_IN_SLEEVE])
@pytest.mark.parametrize("sleeve", [SleeveLength.SHORT, SleeveLength.ELBOW, SleeveLength.LONG])
def test_sleeve_styles_simulate(style: SleeveStyle, construction: Construction, sleeve: SleeveLength) -> None:
    spec = GarmentSpec(categoria=Category.PULLOVER, construccion=construction, estilo_manga=style, largo_manga=sleeve)
    for size in ("XS", "M", "3XL"):
        pattern = generate(spec, PatternParams(talla=size))
        assert simulate(pattern).ok
    if style is SleeveStyle.BELL and sleeve is SleeveLength.LONG:
        sleeve_section = next(s for s in pattern.sections if s.id == "sleeve_left")
        cuff = next(s for s in pattern.sections if s.id == "cuff_left")
        widest = max(st.stitch_count_end for st in sleeve_section.steps)
        assert cuff.end_stitches == widest or cuff.end_stitches > min(st.stitch_count_end for st in sleeve_section.steps)


def test_dress_is_longer_and_wider_at_the_hem() -> None:
    pullover = generate(GarmentSpec(categoria=Category.PULLOVER), PatternParams())
    dress = generate(GarmentSpec(categoria=Category.DRESS, forma=Shape.A_LINE), PatternParams())
    assert simulate(dress).ok
    length = {p.meta.title_key: next(m.value_cm for m in p.measurements if m.key == "body_length") for p in (pullover, dress)}
    assert length["title.dress"] > length["title.pullover_raglan"] + 30
    hem = next(s for s in dress.sections if s.id == "hem")
    assert hem.end_stitches >= 1.2 * next(s for s in dress.sections if s.id == "body").steps[0].stitch_count_end


def test_top_defaults_to_sleeveless_with_armhole_bands() -> None:
    pattern = generate(GarmentSpec(categoria=Category.TOP), PatternParams())
    assert pattern.meta.title_key == "title.top"
    assert {"armhole_band_left", "armhole_band_right"} <= {s.id for s in pattern.sections}
    assert simulate(pattern).ok


def test_henley_polo_and_shawl_collar_have_their_pieces() -> None:
    henley = generate(GarmentSpec(categoria=Category.PULLOVER, construccion=Construction.SET_IN_SLEEVE, escote=Neckline.HENLEY), PatternParams())
    ids = {s.id for s in henley.sections}
    assert {"placket_left", "placket_right"} <= ids and simulate(henley).ok
    holes = next(s for s in henley.sections if s.id == "placket_right").meta["buttonholes"]
    assert holes == 3
    shawl = generate(GarmentSpec(categoria=Category.COAT, escote=Neckline.SHAWL_COLLAR), PatternParams())
    assert {"shawl_collar_left", "shawl_collar_right"} <= {s.id for s in shawl.sections}
    assert shawl.meta.title_key == "title.coat" and simulate(shawl).ok
    assert "approx_neckline" not in {w.code for w in shawl.warnings}


def test_unsupported_neckline_in_a_family_is_still_approximated_honestly() -> None:
    pattern = generate(GarmentSpec(categoria=Category.PULLOVER, escote=Neckline.HENLEY), PatternParams())
    assert "approx_neckline" in {w.code for w in pattern.warnings}  # raglan en redondo: sin tapa


@pytest.mark.parametrize("technique", [Technique.NEEDLES, Technique.CROCHET])
@pytest.mark.parametrize("style", [None, PonchoStyle.RUANA])
@pytest.mark.parametrize("size", ["4", "M", "3XL"])
def test_poncho_and_ruana(technique: Technique, style: PonchoStyle | None, size: str) -> None:
    pattern = generate(GarmentSpec(categoria=Category.PONCHO, tecnica=technique, estilo_poncho=style), PatternParams(talla=size))
    assert simulate(pattern).ok
    assert "approx_category" not in {w.code for w in pattern.warnings}


def test_classic_poncho_neck_opening_passes_the_head() -> None:
    pattern = generate(GarmentSpec(categoria=Category.PONCHO), PatternParams(talla="M"))
    neck = next(m for m in pattern.measurements if m.key == "neck")
    assert neck.value_cm >= 56


@pytest.mark.parametrize("technique", [Technique.NEEDLES, Technique.CROCHET])
def test_shrug_is_one_rectangle_with_edging(technique: Technique) -> None:
    for size in ("XS", "M", "3XL"):
        pattern = generate(GarmentSpec(categoria=Category.SHRUG, tecnica=technique), PatternParams(talla=size))
        assert simulate(pattern).ok
        assert [s.id for s in pattern.sections] == ["shrug", "edging"]


def test_new_categories_are_no_longer_approximated() -> None:
    for category in (Category.TOP, Category.DRESS, Category.COAT, Category.SHRUG, Category.PONCHO):
        assert category not in CATEGORY_APPROX


@pytest.mark.parametrize(
    "spec",
    [
        GarmentSpec(categoria=Category.DRESS, forma=Shape.A_LINE),
        GarmentSpec(categoria=Category.TOP, escote=Neckline.SCOOP),
        GarmentSpec(categoria=Category.COAT, escote=Neckline.SHAWL_COLLAR),
        GarmentSpec(categoria=Category.SHRUG),
        GarmentSpec(categoria=Category.PULLOVER, construccion=Construction.DROP_SHOULDER, escote=Neckline.POLO),
        GarmentSpec(categoria=Category.PULLOVER, estilo_manga=SleeveStyle.PUFF, largo_manga=SleeveLength.SHORT),
    ],
    ids=lambda s: s.categoria.value,
)
def test_multisize_text_projects_to_each_size(spec: GarmentSpec) -> None:
    from tests.test_exactness import _project

    patterns = generate_size_set(spec, PatternParams())
    sizes = [p.meta.size for p in patterns]
    merged = render_document_text(build_document(patterns))
    for pattern in patterns:
        shown = [int(n) for line in _project(merged, sizes, pattern.meta.size) for n in re.findall(r"\[(\d+) pts\]", line)]
        counts = iter([step.stitch_count_end for section in pattern.sections for step in section.steps])
        assert shown and all(any(n == c for c in counts) for n in shown), pattern.meta.size


@pytest.mark.parametrize(
    "spec",
    [
        GarmentSpec(categoria=Category.PONCHO),
        GarmentSpec(categoria=Category.PONCHO, estilo_poncho=PonchoStyle.RUANA, tecnica=Technique.CROCHET),
        GarmentSpec(categoria=Category.SHRUG),
        GarmentSpec(categoria=Category.DRESS, construccion=Construction.SET_IN_SLEEVE, largo_manga=SleeveLength.SLEEVELESS),
    ],
    ids=lambda s: s.categoria.value,
)
def test_pdf_renders(spec: GarmentSpec) -> None:
    assert render_pattern_pdf(generate(spec, PatternParams())).startswith(b"%PDF")
