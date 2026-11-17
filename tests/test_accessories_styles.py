"""D038: estilos de gorro, accesorios nuevos y terminaciones."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.garments import GarmentError, generate
from engine.garments.acc_kit import pompom
from engine.gauge import DEFAULT_GAUGES
from engine.simulator import simulate
from engine.spec import (
    Category,
    Finish,
    GarmentSpec,
    HatStyle,
    PatternParams,
    StitchPatternName,
    Technique,
    YarnWeight,
)
from render.accessories import render_accessory_svg
from render.pdf import render_pattern_pdf

NEW = [
    Category.BALACLAVA,
    Category.HEADBAND,
    Category.FINGERLESS_MITTS,
    Category.LEG_WARMERS,
    Category.BOOTIES,
    Category.SLIPPERS,
]
WEIGHTS = [YarnWeight.FINGERING, YarnWeight.SPORT, YarnWeight.DK, YarnWeight.WORSTED, YarnWeight.BULKY]


@settings(max_examples=150, deadline=None)
@given(
    category=st.sampled_from([Category.MITTENS, Category.SOCKS, Category.HAT, Category.COWL, Category.SCARF, *NEW]),
    technique=st.sampled_from([Technique.NEEDLES, Technique.CROCHET]),
    stitch=st.sampled_from([None, *StitchPatternName]),
    weight=st.sampled_from(WEIGHTS),
    size=st.sampled_from(["XS", "M", "3XL"]),
    style=st.sampled_from([None, *HatStyle]),
)
def test_base_stitch_and_weight_always_simulate(category, technique, stitch, weight, size, style) -> None:  # type: ignore[no-untyped-def]
    """Barrido: antes, mitones con punto arroz fallaban por el multiplo."""
    spec = GarmentSpec(categoria=category, tecnica=technique, punto_base=stitch, estilo_gorro=style if category is Category.HAT else None)
    pattern = generate(spec, PatternParams(talla=size, peso_hilo=weight))
    assert simulate(pattern).ok, simulate(pattern).errors


def test_mittens_seed_stitch_regression() -> None:
    spec = GarmentSpec(categoria=Category.MITTENS, punto_base=StitchPatternName.SEED)
    assert simulate(generate(spec, PatternParams())).ok


@pytest.mark.parametrize("category", NEW)
@pytest.mark.parametrize("technique", [Technique.NEEDLES, Technique.CROCHET])
def test_new_categories_are_real_not_approximated(category: Category, technique: Technique) -> None:
    params = PatternParams(talla="3-6") if category is Category.BOOTIES else PatternParams()
    pattern = generate(GarmentSpec(categoria=category, tecnica=technique), params)
    assert simulate(pattern).ok
    assert "approx_category" not in {w.code for w in pattern.warnings}
    svg = render_accessory_svg(pattern, "es")
    assert "<path" in svg and "acc." not in svg
    assert render_pattern_pdf(pattern).startswith(b"%PDF")


@pytest.mark.parametrize("style", list(HatStyle))
@pytest.mark.parametrize("technique", [Technique.NEEDLES, Technique.CROCHET])
def test_every_hat_style(style: HatStyle, technique: Technique) -> None:
    spec = GarmentSpec(categoria=Category.HAT, tecnica=technique, estilo_gorro=style, acabados=[Finish.POMPOM, Finish.TIES])
    pattern = generate(spec, PatternParams())
    assert simulate(pattern).ok
    assert any(n.key == "acc.finish.pompom" for n in pattern.finishing)
    if style is not HatStyle.BEANIE:
        assert style.value in pattern.meta.family
        assert render_pattern_pdf(pattern).startswith(b"%PDF")


def test_hand_checked_counts() -> None:
    """Cuentas hechas a mano con DK (22 x 30) en talle M (cabeza 56)."""
    slouchy = generate(GarmentSpec(categoria=Category.HAT, estilo_gorro=HatStyle.SLOUCHY), PatternParams())
    # borde 56 x 0,9 x 2,2 = 110,9 -> multiplo de 4: 112; cuerpo 56 x 1,1 x 2,2 = 135,5 -> 8 gajos: 136
    assert (slouchy.section("brim").end_stitches, slouchy.section("body").end_stitches) == (112, 136)
    beret = generate(GarmentSpec(categoria=Category.HAT, estilo_gorro=HatStyle.BERET), PatternParams())
    assert beret.section("body").end_stitches == 184  # 56 x 1,5 x 2,2 = 184,8 en 8 gajos
    mitts = generate(GarmentSpec(categoria=Category.FINGERLESS_MITTS), PatternParams())
    # palma 19 x 0,95 x 2,2 = 39,7 -> 40; cuna 30 % = 12; pulgar 12 + 2
    assert mitts.section("cuff").end_stitches == 40
    assert mitts.section("thumb_gusset").end_stitches == 52
    assert mitts.section("thumb").start_stitches == 14
    legs = generate(GarmentSpec(categoria=Category.LEG_WARMERS), PatternParams())
    # pantorrilla 35 x 2,2 = 77 -> 78; tobillo (22 + 4) x 2,2 = 57,2 -> 58
    assert (legs.section("leg").start_stitches, legs.section("leg").end_stitches) == (78, 58)
    booties = generate(GarmentSpec(categoria=Category.BOOTIES), PatternParams(talla="3-6"))
    assert booties.section("foot").start_stitches == 24  # 10,5 x 1,1 x 2,2 = 25,4 -> multiplo de 4
    bucket = generate(GarmentSpec(categoria=Category.HAT, tecnica=Technique.CROCHET, estilo_gorro=HatStyle.BUCKET), PatternParams())
    assert bucket.section("body").start_stitches == 77  # mpa DK 13,8 pts/10: 56 x 1,38 = 77,3


def test_earflaps_split_the_brim() -> None:
    hat = generate(GarmentSpec(categoria=Category.HAT, acabados=[Finish.EARFLAPS]), PatternParams())
    flap = hat.section("earflap")
    assert hat.meta.family == "hat_earflap"
    assert 2 * flap.start_stitches + flap.meta["front_gap"] + flap.meta["back_gap"] == hat.section("brim").end_stitches


def test_pompom_yarn() -> None:
    made = pompom(DEFAULT_GAUGES["dk"], 8.0)
    assert made.meters == 20.0 and made.wraps == 354


def test_too_thick_yarn_is_an_honest_error() -> None:
    with pytest.raises(GarmentError):
        generate(GarmentSpec(categoria=Category.BOOTIES), PatternParams(talla="0-3", peso_hilo=YarnWeight.SUPER_BULKY))
