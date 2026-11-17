"""Juguetes (amigurumi): toda figura x toda forma de cuerpo x tecnica x grosor."""

from __future__ import annotations

import re
from itertools import pairwise, product

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.document import build_document
from engine.garments import ImpossibleProportionsError, generate
from engine.garments.toy import (
    DEFAULT_HEIGHT_CM,
    FIGURES,
    PARTS,
    PLAN_SIZE,
    SECTORS,
    SIZE_KEYS,
    TEMPLATES,
    resolve_body,
    toy_pieces,
    toy_plan,
)
from engine.i18n import CATALOGS, t
from engine.ir import Pattern
from engine.serialization import pattern_from_dict, pattern_to_dict
from engine.simulator import simulate
from engine.spec import (
    Category,
    Figure,
    GarmentSpec,
    PatternParams,
    Technique,
    ToyBody,
    YarnWeight,
)
from engine.stitches.kinds import StitchKind
from engine.text import render_document_text, render_pattern_text
from render.pdf import render_pattern_pdf
from render.schematic import render_schematic_svg
from render.toy import render_toy_svg

TECHNIQUES = (Technique.CROCHET, Technique.NEEDLES)
WEIGHTS = (YarnWeight.FINGERING, YarnWeight.DK, YarnWeight.SUPER_BULKY)
LANGS = ("es", "en", "fr", "de", "it")
RAW_KEY = re.compile(r"\b(?:pattern|finishing|section|warning|notion|measure|title|desc|doc)\.[a-z]")


def toy(
    figure: Figure | None, technique: Technique = Technique.CROCHET, body: ToyBody | None = None
) -> GarmentSpec:
    return GarmentSpec(categoria=Category.AMIGURUMI, tecnica=technique, figura=figure, cuerpo_juguete=body)


def craft(pattern: Pattern) -> str:
    return "crochet" if pattern.spec.tecnica is Technique.CROCHET else "knit"


def check_structure(pattern: Pattern, figure: Figure, body: ToyBody | None = None) -> None:
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]
    assert pattern.meta.family == "amigurumi"
    used, _ = resolve_body(figure, body)
    assert pattern.spec.cuerpo_juguete is used
    pieces = toy_pieces(figure, used)
    ids = [section.id for section in pattern.sections]
    radial = toy_plan(figure, used) == "radial"
    assert ids == [piece.id for piece in pieces] + (["skirt"] if radial else [])
    sectors = SECTORS[craft(pattern)]  # type: ignore[index]
    for section, piece in zip(pattern.sections, pieces, strict=False):
        assert section.meta["copies"] == piece.copies
        assert section.name_key == piece.name_key
        assert section.name_key.endswith("s") == (piece.copies > 1) or piece.name
        assert section.end_note_keys, section.id
        # Cada pieza crece desde su extremo cerrado en pasos de `sectors` pts.
        counts = [section.start_stitches] + [step.stitch_count_end for step in section.steps]
        assert all(count % sectors == 0 for count in counts[1:])
        if piece.closed:
            assert section.end_stitches == sectors
        if craft(pattern) == "crochet":
            assert section.mode == "round"
            assert section.steps[0].expanded_ops()[0].kind is StitchKind.MAGIC_RING
        else:
            assert section.mode == "flat"
            assert section.meta["cast_on_start"] == 1
            assert section.start_stitches == sectors
            for step in section.steps:  # hileras pares: todo rev
                if step.number % 2 == 0:
                    assert {op.kind for op in step.expanded_ops()} == {StitchKind.PURL}
    if radial:
        skirt = pattern.section("skirt")
        dome = pattern.section("dome")
        assert skirt.start_stitches == dome.meta["max_stitches"]
        assert skirt.end_stitches == dome.meta["max_stitches"] * 3 // 2
    assert pattern.finishing, "falta el armado"


def no_raw_keys(text: str) -> None:
    raw = RAW_KEY.search(text)
    assert raw is None, text[max(0, raw.start() - 60) : raw.end() + 60] if raw else ""


@pytest.mark.parametrize(
    ("figure", "body", "technique", "weight"), list(product(Figure, ToyBody, TECHNIQUES, WEIGHTS))
)
def test_every_figure_body_technique_and_weight_simulates(
    figure: Figure, body: ToyBody, technique: Technique, weight: YarnWeight
) -> None:
    pattern = generate(toy(figure, technique, body), PatternParams(peso_hilo=weight))
    check_structure(pattern, figure, body)
    codes = {w.code for w in pattern.warnings}
    assert not any(code.startswith("approx_") for code in codes)
    used, overridden = resolve_body(figure, body)
    assert ("toy_body_override" in codes) is overridden
    plan = toy_plan(figure, used)
    size = {m.key: m for m in pattern.measurements}[SIZE_KEYS[plan]]
    nominal = DEFAULT_HEIGHT_CM[weight] * PLAN_SIZE[plan]
    assert size.target_cm == pytest.approx(nominal * (0.9 if plan == "ball" else 1.0))


@pytest.mark.parametrize(("figure", "body"), list(product(Figure, ToyBody)))
def test_every_combination_reads_well_in_every_language(figure: Figure, body: ToyBody) -> None:
    for technique in TECHNIQUES:
        pattern = generate(toy(figure, technique, body), PatternParams())
        for lang in LANGS:
            no_raw_keys(render_document_text(build_document([pattern], lang=lang)))
        for note in pattern.finishing:
            assert all(note.key in CATALOGS[lang] for lang in LANGS), note.key


def test_figure_table_is_complete_and_defaults_are_allowed() -> None:
    assert set(FIGURES) == set(Figure)
    for figure, kit in FIGURES.items():
        assert kit.default in kit.bodies, figure
        for kind, factor in kit.parts:
            assert kind in PARTS and factor > 0
        assert f"title.toy_{figure.value}" in CATALOGS["es"]
    # Todas las formas existen al menos para el muneco generico.
    assert FIGURES[Figure.GENERIC].bodies == frozenset(ToyBody)


def test_octopus_is_always_radial_and_says_so_only_if_asked_otherwise() -> None:
    plain = generate(toy(Figure.OCTOPUS), PatternParams())
    assert plain.spec.cuerpo_juguete is ToyBody.RADIAL
    assert "toy_body_override" not in {w.code for w in plain.warnings}
    asked = generate(toy(Figure.OCTOPUS, body=ToyBody.PIECES), PatternParams())
    assert asked.spec.cuerpo_juguete is ToyBody.RADIAL
    override = next(w for w in asked.warnings if w.code == "toy_body_override")
    assert override.message_key == "warning.toy_body_override.radial"
    assert [s.id for s in asked.sections] == ["dome", "tentacle", "skirt"]


def size_factors(plan: str) -> tuple[float, float]:
    # Las cabezas chicas (de pie en dos patas, alargados) no entran en un
    # juguete diminuto: ahi el rango empieza en el tamano por defecto.
    return (1.0, 3.0) if plan in {"biped", "snake", "dachshund"} else (0.5, 3.0)


@settings(max_examples=150, deadline=None)
@given(
    figure=st.sampled_from(list(Figure)),
    body=st.sampled_from(list(ToyBody)),
    weight=st.sampled_from([w for w in YarnWeight if w is not YarnWeight.UNKNOWN]),
    technique=st.sampled_from(TECHNIQUES),
    position=st.floats(min_value=0.0, max_value=1.0),
)
def test_any_reasonable_size_closes(
    figure: Figure, body: ToyBody, weight: YarnWeight, technique: Technique, position: float
) -> None:
    used, _ = resolve_body(figure, body)
    plan = toy_plan(figure, used)
    low, high = size_factors(plan)
    size = DEFAULT_HEIGHT_CM[weight] * PLAN_SIZE[plan] * (low + (high - low) * position)
    key = "length" if plan in {"snake", "dachshund"} else "height"
    pattern = generate(toy(figure, technique, body), PatternParams(peso_hilo=weight, dimensiones_cm={key: size}))
    check_structure(pattern, figure, body)
    measured = {m.key: m for m in pattern.measurements}[SIZE_KEYS[plan]]
    assert measured.target_cm is not None
    assert measured.value_cm == pytest.approx(measured.target_cm, abs=max(1.5, 0.12 * size))


@pytest.mark.parametrize("technique", TECHNIQUES)
def test_too_small_for_the_yarn_is_rejected(technique: Technique) -> None:
    with pytest.raises(ImpossibleProportionsError):
        generate(
            toy(Figure.BEAR, technique),
            PatternParams(peso_hilo=YarnWeight.SUPER_BULKY, dimensiones_cm={"height": 8.0}),
        )


def test_knit_toy_is_knitted_not_routed_to_crochet() -> None:
    pattern = generate(toy(Figure.BEAR, Technique.NEEDLES), PatternParams())
    assert pattern.spec.tecnica is Technique.NEEDLES
    assert pattern.materials.needle_mm is not None and pattern.materials.hook_mm is None
    machine = generate(toy(Figure.BEAR, Technique.MACHINE), PatternParams())
    assert machine.spec.tecnica is Technique.NEEDLES


def test_unknown_figure_is_a_generic_doll_with_a_note() -> None:
    pattern = generate(toy(None), PatternParams())
    assert [s.id for s in pattern.sections] == ["head", "body", "arm", "leg"]
    assert pattern.meta.title_key == "title.toy_generic"
    assert any(w.code == "toy_generic" for w in pattern.warnings)


def test_golden_crochet_bear_dk() -> None:
    """Osito de crochet en DK, 22 cm (verificado a mano).

    Densidad: 14,5 pb CYC x 1,25 = 18,1 pts y 19,9 vtas / 10 cm.
    Cabeza: contorno pi x 0,52 x 22 = 35,9 cm -> 65 pts -> 66 (multiplo de 6),
    10 vueltas de aumento desde el anillo de 6. Largo de polo a polo
    pi x 0,52 x 22 / 2 = 18 cm -> 36 vueltas: 1 anillo + 10 aum + 15 lisas
    + 10 dism. Cuerpo: pi x 0,38 x 22 = 26,3 cm -> 48 pts; cuello 62 % -> 30.
    """
    pattern = generate(toy(Figure.BEAR), PatternParams())
    assert simulate(pattern).ok
    head = pattern.section("head")
    counts = [step.stitch_count_end for step in head.steps]
    assert counts == [*range(6, 67, 6), *[66] * 15, *range(60, 5, -6)]
    body = pattern.section("body")
    assert body.meta["max_stitches"] == 48 and body.end_stitches == 30
    sizes = {s.id: (s.meta["max_stitches"], s.meta["row_count"]) for s in pattern.sections}
    assert sizes == {
        "head": (66, 36),
        "body": (48, 34),
        "arm": (18, 15),
        "leg": (18, 12),
        "ear": (18, 5),
        "muzzle": (24, 6),
        "tail": (12, 6),
    }
    assert pattern.materials.hook_mm == pytest.approx(3.0)
    finishing = {note.key: note.params for note in pattern.finishing}
    assert finishing["finishing.toy.eyes.crochet"] == {"a": 20, "b": 21, "n": 12, "mm": 12}
    assert finishing["finishing.toy.arms.crochet"] == {"a": 32}
    assert finishing["finishing.toy.legs.crochet"] == {"a": 8, "n": 10}


def test_golden_crochet_octopus_dk() -> None:
    """Pulpo de crochet en DK, 22 cm con los tentaculos (verificado a mano).

    Cupula: diametro 0,5 x 22 = 11 cm, contorno 34,6 cm x 1,81 pts/cm =
    62,6 -> 60 pts (multiplo de 6): anillo + 9 vueltas de aumento. Largo de
    polo a polo pi x 11 / 2 = 17,3 cm x 2 vtas/cm -> 35 vueltas: 1 + 9 + 16
    lisas + 9 de cierre. La ultima lisa (vuelta 26) va por la hebra de atras;
    la falda sale de las 60 hebras delanteras: *1 pb, aum* -> 90 pts.
    Ocho tentaculos, uno cada 60 / 8 = 7 pts, dos vueltas por debajo (28).
    Alto: 0,9 x 11,1 + 0,85 x 13,5 = 21,5 cm.
    """
    pattern = generate(toy(Figure.OCTOPUS), PatternParams())
    assert simulate(pattern).ok
    dome = pattern.section("dome")
    counts = [step.stitch_count_end for step in dome.steps]
    assert counts == [*range(6, 61, 6), *[60] * 16, *range(54, 5, -6)]
    assert dome.steps[25].note_key == "pattern.note.toy_skirt_loops.crochet"
    skirt = pattern.section("skirt")
    assert (skirt.start_stitches, skirt.end_stitches) == (60, 90)
    tentacle = pattern.section("tentacle")
    assert tentacle.meta["copies"] == 8 and tentacle.name_key == "section.toy_tentacles"
    finishing = {note.key: note.params for note in pattern.finishing}
    assert finishing["finishing.toy.tentacles.crochet.one"] == {"a": 28, "n": 7}
    assert finishing["finishing.toy.ball_eyes.crochet"] == {"a": 20, "b": 21, "n": 11, "mm": 12}
    height = next(m for m in pattern.measurements if m.key == "toy_height_radial")
    assert height.value_cm == pytest.approx(21.5, abs=0.05)


def test_golden_seamless_neck_narrows_and_widens() -> None:
    """De una pieza: base de 48 pts, cuello al 60 % (30 pts), cabeza de 60."""
    pattern = generate(toy(Figure.UNICORN, body=ToyBody.SEAMLESS), PatternParams())
    piece = pattern.section("head_body")
    counts = [step.stitch_count_end for step in piece.steps]
    neck = counts.index(30, counts.index(48))
    assert max(counts[:neck]) == 48 and max(counts[neck:]) == 60
    assert counts[-1] == 6 and counts[neck + 1] > 30
    keys = [note.key for note in pattern.finishing]
    assert "finishing.toy.horn.crochet.one" in keys and "finishing.toy.mane_unicorn.crochet.one" in keys
    assert "finishing.toy.head_body" not in keys  # no hay costura de cuello


def test_quadruped_has_four_equal_legs_and_head_in_front() -> None:
    pattern = generate(toy(Figure.DOG, body=ToyBody.STANDING), PatternParams())
    leg = pattern.section("leg")
    assert leg.meta["copies"] == 4 and leg.name_key == "section.toy_legs4"
    notes = {note.key: note.params for note in pattern.finishing}
    legs = notes["finishing.toy.legs4.crochet.split"]
    body = pattern.section("body")
    assert 1 < int(legs["b"]) < int(legs["a"]) < body.meta["row_count"]
    assert notes["finishing.toy.head_front.crochet.split"] == {"a": body.meta["row_count"] - 1}


def test_bee_has_stripes_and_snake_has_tongue() -> None:
    bee = generate(toy(Figure.BEE), PatternParams())
    stripes = [s for s in bee.section("ball").steps if s.note_key == "pattern.note.toy_stripe"]
    assert len(stripes) >= 3
    snake = generate(toy(Figure.GENERIC, body=ToyBody.LONG), PatternParams())
    assert [s.id for s in snake.sections] == ["long"]
    assert "finishing.toy.tongue" in {n.key for n in snake.finishing}
    caterpillar = generate(toy(Figure.BEE, body=ToyBody.LONG), PatternParams())
    counts = [s.stitch_count_end for s in caterpillar.section("long").steps]
    dips = sum(1 for a, b in pairwise(counts) if b < a and b < max(counts) * 0.8)
    assert dips >= 4  # segmentos de oruga


def test_golden_knit_bear_dk() -> None:
    """Osito de dos agujas en DK: 8 pts montados, +8 por hilera del derecho."""
    pattern = generate(toy(Figure.BEAR, Technique.NEEDLES), PatternParams())
    assert simulate(pattern).ok
    head = pattern.section("head")
    rs = [step.stitch_count_end for step in head.steps if step.number % 2 == 1]
    assert rs[:10] == list(range(16, 89, 8))
    assert head.end_stitches == 8 and head.steps[-1].number % 2 == 1  # se frunce del derecho
    assert {op.kind for op in head.steps[0].expanded_ops()} == {StitchKind.KFB}
    assert pattern.materials.needle_mm == pytest.approx(3.25)


@pytest.mark.parametrize("technique", TECHNIQUES)
def test_text_reads_like_a_toy_pattern(technique: Technique) -> None:
    pattern = generate(toy(Figure.BEAR, technique), PatternParams())
    text = render_document_text(build_document([pattern]))
    expected_parts = (
        "Cabeza",
        "Brazos (tejer 2)",
        "Orejas (tejer 2)",
        "Hocico",
        "Terminación",
        "Ojos:",
        "Piernas:",
        "relleno",
    )
    for expected in expected_parts:
        assert expected in text, expected
    if technique is Technique.CROCHET:
        assert "Vuelta 1: anillo mágico + 6 pb [6 pts]" in text
        assert "Rellenar firme y seguir rellenando" in text
    else:
        assert "Montar 8 puntos." in text
        assert "Hileras pares (revés de la labor)" in text
        assert "Hilera 1: *kfb; rep desde * hasta el final [16 pts]" in text
    assert "Control: esta parte mide" not in text
    english = render_document_text(build_document([pattern], lang="en"))
    assert "Arms (make 2)" in english and "Finishing" in english
    for rendered in (text, english, render_pattern_text(pattern, lang="es")):
        no_raw_keys(rendered)


@pytest.mark.parametrize(("figure", "body"), list(product(Figure, ToyBody)))
def test_schematic_draws_the_assembled_toy(figure: Figure, body: ToyBody) -> None:
    for technique in TECHNIQUES:
        pattern = generate(toy(figure, technique, body), PatternParams())
        svg = render_toy_svg(pattern, "es")
        assert svg == render_schematic_svg(pattern)
        plan = toy_plan(figure, resolve_body(figure, body)[0])
        side = plan in {"quadruped", "dachshund", "snake"}
        assert ("Vista de costado" if side else "Vista de frente") in svg
        for section in pattern.sections:
            assert t(section.name_key, "es") in svg
        # La cota va afuera del dibujo: a la izquierda (alto) o abajo (largo).
        if plan in {"snake", "dachshund"}:
            assert ">Largo</text>" in svg
        else:
            match = re.search(r'<text x="([0-9.]+)"[^>]*>Altura</text>', svg)
            assert match is not None and float(match.group(1)) < 200


def test_pdf_and_serialization() -> None:
    for spec in (toy(Figure.BUNNY, Technique.NEEDLES), toy(Figure.OCTOPUS), toy(Figure.DOG, body=ToyBody.LONG)):
        pattern = generate(spec, PatternParams())
        assert render_pattern_pdf(pattern).startswith(b"%PDF")
        again = pattern_from_dict(pattern_to_dict(pattern))
        assert again.finishing == pattern.finishing
        assert again.sections == pattern.sections
        assert simulate(again).ok


@pytest.mark.parametrize(("figure", "body"), [(f, b) for f, b in product(Figure, ToyBody) if b is FIGURES[f].default])
def test_round_chart_lists_only_pieces_worked_exactly_like_it(figure: Figure, body: ToyBody) -> None:
    """El dibujo de aumentos vale solo para las piezas que se tejen igual,
    vuelta por vuelta, y sin volver a aumentar despues. Y cada vuelta dibuja
    tantos simbolos como puntos."""
    from engine.blocks import BlockKind
    from engine.document import growth_rounds
    from render.crochet_chart import expand
    from render.toy import render_round_chart_svg

    pattern = generate(toy(figure, Technique.CROCHET, body), PatternParams())
    blocks = build_document([pattern]).blocks
    at = next(i for i, b in enumerate(blocks) if b.kind is BlockKind.ROUND_CHART)
    listed = blocks[at + 1].text
    chart = [s.items for s in growth_rounds(pattern.sections[0].steps)]
    for section in pattern.sections:
        grow = growth_rounds(section.steps)
        same = [s.items for s in grow] == chart[: len(grow)]
        again = max(s.stitch_count_end for s in section.steps) > grow[-1].stitch_count_end
        name = t(section.name_key, "es")
        if not same or again:
            assert name not in listed or any(
                t(other.name_key, "es") == name for other in pattern.sections if other is not section
            ), (section.id, listed)
    for step in growth_rounds(pattern.sections[0].steps):
        assert sum(len(expand(item, StitchKind.SC)) for item in step.items) == step.stitch_count_end
    assert "<svg" in (render_round_chart_svg(pattern, pattern.sections[0].id, "es") or "")


def test_cat_ear_is_not_in_the_round_chart() -> None:
    from engine.blocks import BlockKind

    cat = generate(toy(Figure.CAT), PatternParams())
    blocks = build_document([cat]).blocks
    at = next(i for i, b in enumerate(blocks) if b.kind is BlockKind.ROUND_CHART)
    assert "Cuerpo" in blocks[at + 1].text and "Orejas" not in blocks[at + 1].text


@pytest.mark.parametrize(
    ("figure", "technique", "weight"),
    list(product([Figure.BEAR, Figure.BUNNY, Figure.CAT, Figure.GENERIC], TECHNIQUES, WEIGHTS)),
)
def test_ball_toy_is_one_round_piece_and_verifies(figure: Figure, technique: Technique, weight: YarnWeight) -> None:
    """Un gatito "bolita" no tiene cabeza aparte: una sola pieza redonda,
    con orejas, patitas y cola cosidas segun el animal, y mide lo esperado."""
    spec = toy(figure, technique, ToyBody.BALL)
    pattern = generate(spec, PatternParams(peso_hilo=weight))
    assert simulate(pattern).ok
    ids = {s.id for s in pattern.sections}
    assert "ball" in ids and not ids & {"head", "body", "arm", "leg"}
    assert ("ear" in ids) is (figure is not Figure.GENERIC)
    height = next(m for m in pattern.measurements if m.key == "toy_height_ball")
    assert abs(height.value_cm - height.target_cm) <= height.tolerance_cm  # type: ignore[operator]
    seated = generate(spec.model_copy(update={"cuerpo_juguete": None}), PatternParams(peso_hilo=weight))
    seated_height = next(m for m in seated.measurements if m.key == "toy_height").value_cm
    assert height.value_cm < 0.7 * seated_height  # una bolita es mas chica que un muneco sentado
    text = render_document_text(build_document([pattern]))
    assert "Cabeza" not in text and "sentado" not in text


def test_legacy_templates_still_seated_in_pieces() -> None:
    assert set(TEMPLATES) == {f for f, kit in FIGURES.items() if ToyBody.PIECES in kit.bodies}
    assert [p.id for p in TEMPLATES[Figure.BEAR]] == ["head", "body", "arm", "leg", "ear", "muzzle", "tail"]
