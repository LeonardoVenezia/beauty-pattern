"""Hogar (engine/garments/home.py): piezas planas, fundas, canastos,
almohadones y alfombras, al crochet y a dos agujas."""

from __future__ import annotations

import re
from itertools import pairwise
from math import pi

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.document import build_document
from engine.garments import generate
from engine.garments.home import COZY_ROUND
from engine.garments.home_shapes import change_items, crochet_circle, crochet_oval, knit_circle
from engine.garments.routing import CATEGORY_APPROX
from engine.i18n import t
from engine.i18n.areas.home import TEXTS
from engine.ir import Op, Pattern, Repeat, Step
from engine.serialization import pattern_from_dict, pattern_to_dict
from engine.simulator import simulate
from engine.spec import (
    LANGUAGES,
    Category,
    CozyItem,
    FlatItem,
    FlatShape,
    GarmentSpec,
    PatternParams,
    Technique,
    YarnWeight,
)
from engine.stitches.kinds import StitchKind
from engine.text import render_document_text
from render.home import render_home_svg
from render.pdf import render_pattern_pdf
from render.schematic import render_schematic_svg

HOME = (Category.FLAT_ITEM, Category.COZY, Category.BASKET, Category.PILLOW, Category.RUG)
TECHNIQUES = (Technique.CROCHET, Technique.NEEDLES)
WEIGHTS = [w for w in YarnWeight if w is not YarnWeight.UNKNOWN]
_INCS = {StitchKind.CROCHET_INC, StitchKind.KFB}


def _spec(category: Category, technique: Technique, **sub: object) -> GarmentSpec:
    return GarmentSpec(categoria=category, tecnica=technique, **sub)  # type: ignore[arg-type]


def _check(pattern: Pattern) -> None:
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]
    assert pattern.meta.family.startswith("home_")
    assert not any(w.code.startswith("approx_category") for w in pattern.warnings)


def _kinds(step: Step) -> list[StitchKind]:
    return [op.kind for op in step.expanded_ops()]


def _gaps(step: Step) -> list[int]:
    """Puntos entre aumentos seguidos, contando la vuelta como un anillo."""
    kinds = _kinds(step)
    where = [i for i, kind in enumerate(kinds) if kind in _INCS]
    return [(b - a - 1) % len(kinds) for a, b in zip(where, [*where[1:], where[0] + len(kinds)], strict=True)]


# ---------------------------------------------------------------------------
# Todo se genera y se verifica.
# ---------------------------------------------------------------------------


def test_home_categories_are_no_longer_approximated() -> None:
    assert not set(HOME) & set(CATEGORY_APPROX)


_SUBTYPES = st.one_of(
    st.builds(lambda i, s: (Category.FLAT_ITEM, {"objeto_plano": i, "forma_plana": s}),
              st.sampled_from([*FlatItem, None]), st.sampled_from([*FlatShape, None])),
    st.builds(lambda i: (Category.COZY, {"objeto_funda": i}), st.sampled_from([*CozyItem, None])),
    st.builds(lambda c, s: (c, {"forma_plana": s}),
              st.sampled_from([Category.BASKET, Category.PILLOW, Category.RUG]),
              st.sampled_from([*FlatShape, None])),
)


@settings(max_examples=150, deadline=None)
@given(
    sub=_SUBTYPES,
    technique=st.sampled_from(TECHNIQUES),
    weight=st.sampled_from(WEIGHTS),
    scale=st.floats(min_value=0.8, max_value=1.6),
)
def test_every_home_piece_simulates(
    sub: tuple[Category, dict[str, object]], technique: Technique, weight: YarnWeight, scale: float
) -> None:
    category, fields = sub
    base = generate(_spec(category, technique, **fields), PatternParams(peso_hilo=weight))
    # Con medidas propias (todas mas grandes o mas chicas) tambien cierra.
    dims = {m.key: m.value_cm * scale for m in base.measurements if m.key in {"width", "length", "diameter", "height"}}
    if category is Category.COZY and "diameter" not in dims and base.meta.family == "home_cozy":
        dims["diameter"] = base.measurements[0].value_cm / pi * scale
    pattern = generate(_spec(category, technique, **fields), PatternParams(peso_hilo=weight, dimensiones_cm=dims))
    for each in (base, pattern):
        _check(each)
        assert render_home_svg(each, "es").startswith("<svg")
        assert render_document_text(build_document([each]))


@pytest.mark.parametrize("category", HOME)
@pytest.mark.parametrize("technique", TECHNIQUES)
def test_texts_and_drawings_exist_in_every_language(category: Category, technique: Technique) -> None:
    pattern = generate(_spec(category, technique), PatternParams())
    for lang in LANGUAGES:
        text = render_document_text(build_document([pattern], lang=lang))
        svg = render_home_svg(pattern, lang)
        for blob in (text, svg):
            leftover = re.findall(r"\b(?:home|measure|section|title|schematic|finishing|warning|notion|desc)\.[a-z_.]+", blob)
            assert not leftover, (lang, leftover)
    assert render_schematic_svg(pattern) == render_home_svg(pattern, "es")


def test_area_texts_have_the_same_keys_and_placeholders() -> None:
    keys = set(TEXTS["es"])
    for lang, texts in TEXTS.items():
        assert set(texts) == keys, lang
        for key, text in texts.items():
            assert set(re.findall(r"{(\w+)}", text)) == set(re.findall(r"{(\w+)}", TEXTS["es"][key])), (lang, key)


# ---------------------------------------------------------------------------
# Exactitud geometrica.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("kind", "inc"), [(StitchKind.SC, 6), (StitchKind.HDC, 8), (StitchKind.DC, 12)])
def test_crochet_circle_increases_are_even_and_staggered(kind: StitchKind, inc: int) -> None:
    steps = crochet_circle(kind, inc, 20)
    for number, step in enumerate(steps, start=1):
        assert step.stitch_count_end == inc * number
        if number == 1:
            continue
        assert sum(1 for k in _kinds(step) if k is StitchKind.CROCHET_INC) == inc
        assert set(_gaps(step)) == {number - 2}, number  # tramos iguales
    # En las vueltas pares el primer aumento se corre medio tramo.
    first = [_kinds(s).index(StitchKind.CROCHET_INC) for s in steps[5:7]]
    assert first[0] != first[1]


def test_knit_circle_grows_in_eight_even_sectors() -> None:
    steps = knit_circle(96, 22, edge=2)
    counts = [s.stitch_count_end for s in steps]
    assert counts[0] == 8 and counts[-1] == 96
    for before, step in zip(counts, steps[1:], strict=False):
        delta = step.stitch_count_end - before
        assert delta in {0, 8}
        if delta:
            assert len(set(_gaps(step))) == 1
    assert _kinds(steps[-2]) == [StitchKind.PURL] * 96  # borde en punto bobo


@pytest.mark.parametrize(("kind", "k"), [(StitchKind.SC, 3), (StitchKind.HDC, 4), (StitchKind.DC, 6)])
def test_crochet_oval_keeps_straight_sides_and_grows_at_both_ends(kind: StitchKind, k: int) -> None:
    straight = 15
    steps, _head, end = crochet_oval(kind, straight, k, 12)
    assert steps[0].stitch_count_end == straight + 2  # cadena
    assert steps[1].stitch_count_end == 2 * straight + 2 * k
    for before, step in pairwise(steps[1:]):
        assert step.stitch_count_end - before.stitch_count_end == 2 * k
        kinds = _kinds(step)
        assert sum(1 for x in kinds if x is StitchKind.CROCHET_INC) == 2 * k
    # Los dos extremos terminan iguales y suman con los lados rectos.
    assert steps[-1].stitch_count_end == 2 * straight + 2 * end
    assert end == k * 12


def test_change_items_decreases_evenly() -> None:
    items = change_items(36, 6, StitchKind.SC, StitchKind.CROCHET_DEC)
    assert items == [Repeat(6, (Op(StitchKind.SC, times=4), Op(StitchKind.CROCHET_DEC)))]


@pytest.mark.parametrize("technique", TECHNIQUES)
@pytest.mark.parametrize("weight", WEIGHTS)
def test_square_has_equal_sides(technique: Technique, weight: YarnWeight) -> None:
    pattern = generate(
        _spec(Category.FLAT_ITEM, technique, objeto_plano=FlatItem.DISHCLOTH, forma_plana=FlatShape.SQUARE),
        PatternParams(peso_hilo=weight),
    )
    _check(pattern)
    width = next(m.value_cm for m in pattern.measurements if m.key == "width")
    length = next(m.value_cm for m in pattern.measurements if m.key == "length")
    gauge = pattern.params.densidad
    assert gauge is not None
    # Un cuadrado: los lados difieren a lo sumo en un punto o un lomo/hilera.
    assert abs(width - length) <= max(1 / gauge.stitches_per_cm, 2 / gauge.rows_per_cm) + 1e-9


@pytest.mark.parametrize("weight", WEIGHTS)
def test_rectangle_sides_match_the_asked_size(weight: YarnWeight) -> None:
    params = PatternParams(peso_hilo=weight, dimensiones_cm={"width": 45, "length": 32})
    for technique in TECHNIQUES:
        pattern = generate(_spec(Category.FLAT_ITEM, technique, objeto_plano=FlatItem.PLACEMAT), params)
        _check(pattern)  # el simulador compara ancho y largo con lo pedido
        section = pattern.sections[0]
        assert section.mode == "flat"
        assert {s.stitch_count_end for s in section.steps} == {section.end_stitches}


def test_knit_oval_is_a_rectangle_and_says_so() -> None:
    pattern = generate(
        _spec(Category.FLAT_ITEM, Technique.NEEDLES, objeto_plano=FlatItem.PLACEMAT, forma_plana=FlatShape.OVAL),
        PatternParams(),
    )
    _check(pattern)
    assert "home_knit_oval" in {w.code for w in pattern.warnings}
    assert pattern.sections[0].mode == "flat"


# ---------------------------------------------------------------------------
# Fundas.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("technique", TECHNIQUES)
@pytest.mark.parametrize("item", list(COZY_ROUND))
def test_round_cozy_hugs_and_has_a_closed_bottom(technique: Technique, item: CozyItem) -> None:
    pattern = generate(_spec(Category.COZY, technique, objeto_funda=item), PatternParams())
    _check(pattern)
    base, walls = pattern.sections[:2]
    first = base.steps[0].expanded_ops()[0].kind
    assert first in {StitchKind.RING, StitchKind.CAST_ON}  # fondo cerrado desde el centro
    assert walls.start_stitches == base.end_stitches
    diameter = COZY_ROUND[item][0]
    circ = next(m for m in pattern.measurements if m.key == "circumference")
    assert circ.value_cm < pi * diameter  # holgura negativa: abraza
    if item is CozyItem.MATE and technique is Technique.CROCHET:
        top = next(m for m in pattern.measurements if m.key == "home_top")
        assert top.value_cm < circ.value_cm  # se cierra hacia la boca
    if item is CozyItem.THERMOS:
        assert pattern.sections[-1].id == "strap"


def test_mate_cozy_follows_the_users_mate() -> None:
    small = generate(_spec(Category.COZY, Technique.CROCHET, objeto_funda=CozyItem.MATE), PatternParams())
    big = generate(
        _spec(Category.COZY, Technique.CROCHET, objeto_funda=CozyItem.MATE),
        PatternParams(dimensiones_cm={"diameter": 10, "height": 11, "top_diameter": 10}),
    )
    _check(big)
    assert big.sections[1].start_stitches > small.sections[1].start_stitches
    assert "home_top" not in {m.key for m in big.measurements}  # boca igual al cuerpo: recta


def test_golden_crochet_mate_dk() -> None:
    """A mano: pb DK 14,5 pts x 16 vtas; contorno pi x 8 x 0,95 = 23,9 cm =
    34,6 pts -> 36 (6 gajos); boca pi x 6,5 x 0,95 = 19,4 cm = 28,1 -> 30;
    alto 9 cm = 14,4 -> 14 vueltas; base de 6 vueltas (6, 12 ... 36)."""
    pattern = generate(_spec(Category.COZY, Technique.CROCHET, objeto_funda=CozyItem.MATE), PatternParams())
    base, walls = pattern.sections
    assert [s.stitch_count_end for s in base.steps] == [6, 12, 18, 24, 30, 36]
    assert len(walls.steps) == 14
    assert walls.steps[0].note_key == "home.note.walls_blo"
    assert walls.end_stitches == 30
    assert sum(1 for s in walls.steps if s.stitch_count_end < s.consumes) == 1


def test_golden_crochet_coaster_dk() -> None:
    """A mano: pb DK 14,5 x 16; 2 pi x 1,45 / 1,6 = 5,7 -> 6 aum por vuelta;
    10 cm de diametro = 5 cm de radio x 1,6 = 8 vueltas -> 48 pts."""
    pattern = generate(_spec(Category.FLAT_ITEM, Technique.CROCHET, objeto_plano=FlatItem.COASTER), PatternParams())
    counts = [s.stitch_count_end for s in pattern.sections[0].steps]
    assert counts == [6 * r for r in range(1, 9)]


@pytest.mark.parametrize("item", [CozyItem.PHONE, CozyItem.GLASSES, CozyItem.PENCIL_CASE, CozyItem.LAPTOP])
def test_pouches(item: CozyItem) -> None:
    crochet = generate(_spec(Category.COZY, Technique.CROCHET, objeto_funda=item), PatternParams())
    knit = generate(_spec(Category.COZY, Technique.NEEDLES, objeto_funda=item), PatternParams())
    for pattern in (crochet, knit):
        _check(pattern)
        assert pattern.meta.family == "home_pouch"
    pouch = crochet.sections[0]
    chain = pouch.steps[0].stitch_count_end
    assert pouch.steps[1].stitch_count_end == 2 * chain  # fondo cerrado sin costura
    keys = {n.key for n in crochet.finishing}
    assert ("finishing.home.zipper" in keys) == (item is CozyItem.PENCIL_CASE)
    assert ("flap" in {s.id for s in crochet.sections}) == (item is CozyItem.LAPTOP)


# ---------------------------------------------------------------------------
# Canasto, almohadon, alfombra, agarradera.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("technique", TECHNIQUES)
@pytest.mark.parametrize("shape", [FlatShape.CIRCLE, FlatShape.RECTANGLE, FlatShape.OVAL])
def test_basket_handles_are_opposite(technique: Technique, shape: FlatShape) -> None:
    pattern = generate(_spec(Category.BASKET, technique, forma_plana=shape), PatternParams(peso_hilo=YarnWeight.BULKY))
    _check(pattern)
    walls = pattern.sections[1]
    opened = next(s for s in walls.steps if s.note_key == "home.note.handles_open")
    index = walls.steps.index(opened)
    kinds = _kinds(opened)
    hole = StitchKind.SKIP if technique is Technique.CROCHET else StitchKind.BIND_OFF
    consumed: list[int] = []
    position = 0
    for op in opened.expanded_ops():
        if op.kind is hole:
            consumed.append(position)
        position += op.consumes
    assert kinds.count(hole) == len(consumed) and len(consumed) % 2 == 0
    width = len(consumed) // 2
    count = opened.consumes
    assert consumed[width] - consumed[0] == count // 2  # una frente a la otra
    assert walls.steps[index + 1].stitch_count_end == count


def test_low_basket_has_no_handles() -> None:
    pattern = generate(_spec(Category.BASKET, Technique.CROCHET), PatternParams(dimensiones_cm={"height": 8}))
    _check(pattern)
    assert not any(s.note_key == "home.note.handles_open" for s in pattern.sections[1].steps)


def test_knit_pillow_has_an_envelope_back_that_matches_the_front() -> None:
    pattern = generate(_spec(Category.PILLOW, Technique.NEEDLES), PatternParams())
    _check(pattern)
    front, back = pattern.sections
    assert back.meta["copies"] == 2 and back.end_stitches == front.end_stitches
    insert = 40.0
    width = next(m for m in pattern.measurements if m.key == "width")
    assert width.target_cm == insert - 2


def test_potholder_is_double_with_a_hanging_loop() -> None:
    for technique in TECHNIQUES:
        pattern = generate(_spec(Category.FLAT_ITEM, technique, objeto_plano=FlatItem.POTHOLDER), PatternParams())
        _check(pattern)
        assert pattern.sections[0].meta["copies"] == 2
        assert any(n.key.startswith("finishing.home.hanging_loop") for n in pattern.finishing)


def test_crochet_doily_with_a_motif_uses_the_motif_engine() -> None:
    from engine.spec import MotifBand, MotifDesign, MotifStitch

    motif = MotifDesign(bandas=[MotifBand(punto=MotifStitch.DC), MotifBand(punto=MotifStitch.MESH)])
    pattern = generate(
        _spec(Category.FLAT_ITEM, Technique.CROCHET, objeto_plano=FlatItem.DOILY, motivo=motif), PatternParams()
    )
    assert pattern.meta.family == "crochet_motif"
    assert simulate(pattern).ok


def test_garter_gauge_is_named_in_the_document() -> None:
    pattern = generate(_spec(Category.FLAT_ITEM, Technique.NEEDLES), PatternParams())
    text = render_document_text(build_document([pattern]))
    assert t("doc.gauge_stitch_garter", "es") in text


@pytest.mark.parametrize("category", HOME)
def test_pdf_and_serialization(category: Category) -> None:
    pattern = generate(_spec(category, Technique.CROCHET), PatternParams())
    assert render_pattern_pdf(pattern).startswith(b"%PDF")
    again = pattern_from_dict(pattern_to_dict(pattern))
    assert again.sections == pattern.sections
    assert simulate(again).ok
