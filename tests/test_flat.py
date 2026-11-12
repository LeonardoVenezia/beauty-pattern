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
    Neckline,
    PatternParams,
    SleeveLength,
    Technique,
    Texture,
    TextureObservation,
    YarnWeight,
)
from engine.stitches.kinds import StitchKind
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
    # Escote redondo: el delantero cierra el centro y cada hombro queda con
    # los mismos 33 pts que la espalda deja a cada lado ((110 - 44) / 2).
    assert counts(pattern) == {
        "back": (0, 110),
        "front": (0, 84),
        "neck_right": (42, 33),
        "neck_left": (42, 33),
        "sleeve_left": (0, 76),
        "cuff_left": (0, 76),
        "sleeve_right": (0, 76),
        "cuff_right": (0, 76),
        "neckband": (0, 102),
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
    assert "Tapa de botones izquierda" in text and "Tapa de botones derecha" in text
    svg = render_schematic_svg(pattern)
    assert "<svg" in svg
    # Esquema de prenda con cotas (letra + medida) y la abertura del frente.
    assert "cm" in svg
    assert "stroke-dasharray" in svg
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


@pytest.mark.parametrize("neckline", [None, Neckline.CREW], ids=["v", "crew"])
def test_cardigan_fronts_shape_the_neck_and_match_the_back_shoulder(neckline: Neckline | None) -> None:
    spec = spec_for(Category.CARDIGAN).model_copy(update={"escote": neckline})
    pattern = generate(spec, PatternParams(talla="M"))
    assert simulate(pattern).ok
    by_id = {section.id: section for section in pattern.sections}
    shoulder = by_id["back"].meta["shoulder"]
    assert by_id["left_front"].end_stitches == by_id["right_front"].end_stitches == shoulder
    assert "no_neck_shaping" not in {w.code for w in pattern.warnings}
    right = by_id["right_front"].steps
    shaped = [s for s in right if any(getattr(i, "kind", None) in {StitchKind.SSK, StitchKind.BIND_OFF} for i in s.items)]
    # Delantero derecho: el escote esta al comienzo de las hileras del LD.
    assert all(s.number % 2 == 1 or s.items[0].kind is StitchKind.BIND_OFF for s in shaped)
    if neckline is None:  # V: disminuciones repartidas, sin cierre
        assert not any(getattr(i, "kind", None) is StitchKind.BIND_OFF for s in right for i in s.items)


def test_cardigan_cable_panel_stays_clear_of_the_v_neck() -> None:
    spec = spec_for(Category.CARDIGAN).model_copy(
        update={"texturas": [TextureObservation(textura=Texture.CABLES)]}
    )
    for size in ("XS", "M", "3XL"):
        pattern = generate(spec, PatternParams(talla=size, peso_hilo=YarnWeight.BULKY))
        assert simulate(pattern).ok


def test_cardigan_v_neck_text_repeats_the_shaping_cycle() -> None:
    """Las disminuciones del escote se escriben una vez con su "Repetir"."""
    spec = spec_for(Category.CARDIGAN).model_copy(update={"texturas": [TextureObservation(textura=Texture.CABLES)]})
    text = render_pattern_text(generate(spec, PatternParams(talla="M")), lang="es")
    front = text[text.index("Delantero izquierdo") : text.index("Delantero derecho")]
    assert "Repetir las últimas 4 hileras" in front
    assert front.count("2pjd") <= 4


@pytest.mark.parametrize("stitches", range(1, 30))
def test_hem_rib_is_2x2_for_any_count(stitches: int) -> None:
    from engine.garments.rows import hem_rib_row
    from engine.ir import Op, Repeat

    def flat(row: int) -> list[StitchKind]:
        out: list[StitchKind] = []
        for item in hem_rib_row(stitches, row):
            ops = item.ops * item.times if isinstance(item, Repeat) else (item,)
            for op in ops:
                assert isinstance(op, Op)
                out += [op.kind] * op.times
        return out

    rs, ws = flat(1), flat(2)
    assert len(rs) == len(ws) == stitches
    # LR = los pts como se presentan: el espejo del LD con der/rev invertidos.
    assert ws == [StitchKind.PURL if k is StitchKind.KNIT else StitchKind.KNIT for k in reversed(rs)]
    assert rs[: min(4, stitches)] == [StitchKind.KNIT, StitchKind.KNIT, StitchKind.PURL, StitchKind.PURL][: min(4, stitches)]
