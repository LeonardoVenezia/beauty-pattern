"""CLI generar-patron: ejemplos y mensajes de error con archivo y campo."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.generar_patron import main

EXAMPLES = sorted(Path(__file__).resolve().parent.parent.joinpath("examples").glob("*.yaml"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_examples_generate_pdf(path: Path, tmp_path: Path) -> None:
    out = tmp_path / "p.pdf"
    assert main([str(path), "--salida", str(out), "--talle", "M"]) == 0
    assert out.read_bytes().startswith(b"%PDF")


def test_bad_field_reports_file_and_field(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "malo.yaml"
    bad.write_text("spec:\n  categoria: pullover\n  tecnica: tejido_magico\n", encoding="utf-8")
    assert main([str(bad)]) == 2
    err = capsys.readouterr().err
    assert "malo.yaml" in err and "spec.tecnica" in err


def test_unknown_size_reports_available(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = EXAMPLES[[p.stem for p in EXAMPLES].index("sueter-raglan")]
    assert main([str(path), "--salida", str(tmp_path / "x.pdf"), "--talle", "XXS"]) == 2
    assert "XS, S, M" in capsys.readouterr().err
