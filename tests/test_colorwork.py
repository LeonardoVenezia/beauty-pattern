"""Guardas de jacquard del canesu: motivos, ubicacion, texto, grafico y PDF."""

from __future__ import annotations

from itertools import groupby, product

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.colorwork import (
    MAX_FLOAT,
    MOTIFS,
    ROLE_MOTIFS,
    ColorworkChart,
    color_name,
    max_float,
    pick_motif,
)
from engine.document import build_document
from engine.garments import generate
from engine.garments.yoke import yoke_bands
from engine.ir import Op, Pattern, Section
from engine.simulator import simulate
from engine.sizes import BODY_SIZES
from engine.spec import (
    Category,
    Colorwork,
    ColorworkType,
    Construction,
    GarmentSpec,
    PatternParams,
    Technique,
    YarnWeight,
)
from engine.stitches.kinds import StitchKind
from engine.text import render_document_text, render_pattern_text
from render.colorwork import render_colorwork_chart_svg
from render.pdf import render_pattern_pdf

PALETTE = ["#f2eee0", "#1f3a5f", "#b03a2e"]


def fair_isle(palette: list[str] | None = None) -> GarmentSpec:
    return GarmentSpec(
        categoria=Category.PULLOVER,
        tecnica=Technique.CIRCULAR,
        construccion=Construction.YOKE,
        colorwork=Colorwork(tipo=ColorworkType.FAIR_ISLE, paleta=PALETTE if palette is None else palette),
    )


def _yoke(pattern: Pattern) -> Section:
    return next(s for s in pattern.sections if s.id == "yoke")


# --- Biblioteca de motivos -----------------------------------------------------


@pytest.mark.parametrize(("motif", "height"), list(product(MOTIFS, range(1, 14))))
def test_motifs_respect_float_limit_and_height(motif: str, height: int) -> None:
    rows = MOTIFS[motif](height)
    if rows is None:
        return
    assert 1 <= len(rows) <= height
    assert len({len(r) for r in rows}) == 1
    for row in rows:
        assert set(row) <= {"#", "."}
        assert max_float(row) <= MAX_FLOAT, (motif, height, row)
    assert any("#" in row for row in rows)


@pytest.mark.parametrize(("role", "height"), list(product(ROLE_MOTIFS, range(0, 14))))
def test_pick_motif_fits_the_budget(role: str, height: int) -> None:
    picked = pick_motif(role, height)
    if height < 1:
        assert picked is None
        return
    assert picked is not None
    key, rows = picked
    assert key in ROLE_MOTIFS[role]
    assert len(rows) <= height
    if role == "border":
        assert 4 % len(rows[0]) == 0  # divide el conteo final del canesu


def test_max_float_is_circular() -> None:
    assert max_float("#.....") == 5
    assert max_float("..#...") == 5  # el tramo da la vuelta
    assert max_float("......") == 0  # un solo color: sin flotes
    assert max_float("#.#.") == 1


def test_color_names() -> None:
    assert color_name("#f2eee0", "es") == "crudo"
    assert color_name("#1f3a5f", "es") == "azul oscuro"
    assert color_name("#1f3a5f", "en") == "dark blue"
    assert color_name("#b03a2e", "es") == "rojo"
    assert color_name("not-a-color", "es") == "not-a-color"


# --- Ubicacion de las guardas en el canesu --------------------------------------


def _band_runs(section: Section) -> list[tuple[str, list[int]]]:
    """(numero de grafico, indices de paso) de cada guarda, en orden."""
    runs: list[tuple[str, list[int]]] = []
    indexed = list(enumerate(section.steps))
    for key, group in groupby(
        indexed,
        key=lambda pair: dict(pair[1].note_params).get("n") if pair[1].note_key == "pattern.note.yoke_chart" else None,
    ):
        if key is not None:
            runs.append((key, [index for index, _ in group]))
    return runs


@pytest.mark.parametrize(("size", "weight"), list(product(BODY_SIZES, YarnWeight)))
def test_fair_isle_yoke_bands_are_consistent_with_the_ir(size: str, weight: YarnWeight) -> None:
    params = PatternParams(talla=size, peso_hilo=weight)
    pattern = generate(fair_isle(), params)
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]

    bands = yoke_bands(fair_isle(), params)
    assert bands, "todo grosor tiene al menos una guarda"
    charts = {str(band.chart.number): band.chart for band in bands}
    yoke = _yoke(pattern)
    assert yoke.meta["colorwork_bands"] == len(bands)
    runs = _band_runs(yoke)
    assert [n for n, _ in runs] == [str(band.chart.number) for band in bands]
    for n, indices in runs:
        chart = charts[n]
        assert len(indices) == chart.height
        assert indices == list(range(indices[0], indices[0] + chart.height))
        before, after = yoke.steps[indices[0] - 1], yoke.steps[indices[-1] + 1]
        # Una vuelta lisa antes (despues del aumento) y otra despues.
        assert before.note_key == "pattern.note.plain"
        assert after.note_key == "pattern.note.plain"
        for index in indices:
            step = yoke.steps[index]
            assert step.consumes % chart.width == 0
            assert step.items == (Op(StitchKind.KNIT, times=step.consumes),)
            assert step.stitch_count_end == step.consumes
            params_ = dict(step.note_params)
            assert params_["chart_repeat"] == str(chart.width)
            assert params_["reps"] == str(step.consumes // chart.width)
            assert params_["rows"] == str(chart.height)

    assert len(pattern.materials.color_meters) == len(pattern.materials.colors)
    used = {band.chart.contrast for band in bands}
    for index in used:
        assert pattern.materials.color_meters[index] > 0


@pytest.mark.parametrize("weight", list(YarnWeight))
def test_charts_are_the_same_for_every_size(weight: YarnWeight) -> None:
    layouts = {
        tuple((b.stretch, b.chart) for b in yoke_bands(fair_isle(), PatternParams(talla=size, peso_hilo=weight)))
        for size in BODY_SIZES
    }
    assert len(layouts) == 1


@settings(max_examples=25, deadline=None)
@given(
    palette=st.lists(st.from_regex(r"#[0-9a-f]{6}", fullmatch=True), min_size=0, max_size=5, unique=True),
    size=st.sampled_from(list(BODY_SIZES)),
    weight=st.sampled_from([YarnWeight.FINGERING, YarnWeight.DK, YarnWeight.WORSTED, YarnWeight.BULKY]),
)
def test_any_palette_gives_a_valid_charted_yoke(palette: list[str], size: str, weight: YarnWeight) -> None:
    pattern = generate(fair_isle(palette), PatternParams(talla=size, peso_hilo=weight))
    assert simulate(pattern).ok
    colors = pattern.materials.colors
    assert len(colors) >= 2
    for band in yoke_bands(fair_isle(palette), pattern.params):
        assert band.chart.background == 0
        assert 0 < band.chart.contrast < len(colors)


def test_bands_shift_after_a_texture_panel_chart() -> None:
    from engine.spec import StitchPatternName

    spec = fair_isle().model_copy(update={"punto_base": StitchPatternName.CABLES})
    pattern = generate(spec, PatternParams(talla="M"))
    assert simulate(pattern).ok
    assert any("panel_rows" in s.meta for s in pattern.sections)
    document = build_document([pattern])
    assert len(document.charts) == 1  # grafico 1: el panel de trenzas
    assert [c.number for c in document.colorwork_charts] == list(range(2, 2 + len(document.colorwork_charts)))


# --- Texto multitalle, grafico y PDF --------------------------------------------


def test_multisize_text_references_the_charts() -> None:
    patterns = [generate(fair_isle(), PatternParams(talla=size)) for size in BODY_SIZES]
    document = build_document(patterns)
    text = render_document_text(document)
    yoke = text[text.index("Canesú\n") : text.index("Cuerpo\n")]
    assert "Solo talles" not in yoke
    assert yoke.count("Vuelta de aumentos repartidos") == 6
    assert "gráfico de jacquard" not in text
    for chart in document.colorwork_charts:
        assert f"del gráfico {chart.number}, repitiendo" in yoke
        assert f"Gráfico {chart.number}: " in text
    charts_part = text[text.index("Gráficos\n") :]
    first = document.colorwork_charts[0]
    # Grafico en texto: la vuelta mas alta arriba, numero de vuelta a la derecha.
    assert charts_part.splitlines()[2].endswith(f"  {first.height}")
    assert "Metraje por color" in text
    assert "A: crudo (#f2eee0)" in text


def test_english_text() -> None:
    pattern = generate(fair_isle(), PatternParams(talla="M", idioma="en"))
    text = render_document_text(build_document([pattern]))
    assert "of chart 1, repeating the" in text
    assert "Chart 1: " in text


def test_chart_svg_has_colors_symbols_numbers_and_legend() -> None:
    chart = ColorworkChart(number=2, motif="diamond", rows=MOTIFS["diamond"](5) or (), background=0, contrast=1)
    svg = render_colorwork_chart_svg(chart, tuple(PALETTE), lang="es")
    assert svg.startswith("<svg")
    assert "Gráfico 2: rombos" in svg
    assert 'fill="#1f3a5f"' in svg and 'fill="#f2eee0"' in svg
    assert "<line" in svg  # simbolo del contraste para imprimir en B/N
    assert "repetición de 6 pts" in svg
    assert "A: crudo \u2013 fondo" in svg
    assert "B: azul oscuro" in svg
    named = render_colorwork_chart_svg(chart, ("azul denim", "blanco"), lang="es")
    assert "A: azul denim" in named and 'fill="#6f8fbf"' in named  # la IA nombra los colores con palabras
    for row in range(1, chart.height + 1):
        assert f">{row}</text>" in svg


def test_chart_color_at_reads_right_to_left() -> None:
    chart = ColorworkChart(number=1, motif="dots", rows=("#...", "..#."), background=0, contrast=2)
    assert chart.color_at(1, 4) == 2  # columna 1 = derecha
    assert chart.color_at(1, 1) == 0
    assert chart.color_at(2, 2) == 2


def test_pdf_renders_with_colorwork_charts() -> None:
    pattern = generate(fair_isle(), PatternParams(talla="M", peso_hilo=YarnWeight.DK))
    pdf = render_pattern_pdf(pattern)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 10_000


def test_simulator_rejects_a_chart_repeat_that_does_not_fit() -> None:
    from dataclasses import replace

    pattern = generate(fair_isle(), PatternParams(talla="M"))
    yoke = _yoke(pattern)
    index = next(i for i, s in enumerate(yoke.steps) if s.note_key == "pattern.note.yoke_chart")
    step = yoke.steps[index]
    bad_width = next(w for w in range(3, 50) if step.consumes % w)
    params_ = tuple((k, str(bad_width) if k == "chart_repeat" else v) for k, v in step.note_params)
    steps = (*yoke.steps[:index], replace(step, note_params=params_), *yoke.steps[index + 1 :])
    sections = tuple(replace(s, steps=steps) if s.id == "yoke" else s for s in pattern.sections)
    report = simulate(replace(pattern, sections=sections))
    assert not report.ok
    assert any(issue.code == "chart_repeat" for issue in report.errors)


def test_palette_names_follow_the_pattern_language() -> None:
    """La IA nombra los colores en espanol: un PDF en aleman no puede decir
    "azul denim". El color base se traduce y el dibujo sigue pintandolo."""
    from engine.colorwork import translate_color
    from render.draw import swatch

    assert translate_color("azul denim", "de") == "blau"
    assert translate_color("verde oscuro", "fr") == "vert foncé"
    assert translate_color("azul denim", "es") == "azul denim"
    assert translate_color("#aabbcc", "it") == "#aabbcc"
    assert swatch("blau") == swatch("azul") == swatch("blue")
    spec = fair_isle().model_copy(
        update={"colorwork": fair_isle().colorwork.model_copy(update={"paleta": ["azul denim", "blanco"]})}  # type: ignore[union-attr]
    )
    text = render_pattern_text(generate(spec, PatternParams(idioma="de")), lang="de")
    assert "blanco" not in text and "azul" not in text
