"""La rubrica de evals/run_photos sin IA: se le pasa lo que 'vio' la IA."""

from __future__ import annotations

from engine.spec import Category, Construction, GarmentSpec, Technique
from evals.run_photos import field_scores, rubric, summarize, to_markdown

SEEN = GarmentSpec(
    categoria=Category.PULLOVER,
    tecnica=Technique.CIRCULAR,
    construccion=Construction.RAGLAN_TOP_DOWN,
    texturas=[{"textura": "cables"}],
)


def test_field_scores_compare_expected_values() -> None:
    expected = {"categoria": "pullover", "construccion": "yoke", "texturas": ["cables"]}
    assert field_scores(expected, SEEN) == {"categoria": True, "construccion": False, "texturas": True}


def test_rubric_passes_for_supported_textured_sweater() -> None:
    checks = rubric({"categoria": "pullover", "texturas": ["cables"]}, SEEN)
    assert all(checks.values()), checks


def test_rubric_flags_missing_texture_and_wrong_category() -> None:
    plain = GarmentSpec(categoria=Category.CARDIGAN, tecnica=Technique.NEEDLES)
    checks = rubric({"categoria": "pullover", "texturas": ["lace"]}, plain)
    assert not checks["textura_en_el_patron"]
    assert not checks["categoria_correcta"]


def test_report_markdown_lists_failures() -> None:
    rows = [{"id": "a", "campos": {"categoria": False}, "rubrica": {"familia_soportada": True}}]
    text = to_markdown(summarize(rows, "extractor-v2", "modelo"))
    assert "`a`: categoria" in text
