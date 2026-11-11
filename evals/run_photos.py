"""Evaluacion con fotos reales: IA por campo + rubrica del patron resultante.

La IA solo interpreta la foto; el patron sale del motor. Por eso se mide por
separado: (1) que la IA vea bien (precision por campo contra lo esperado) y
(2) que el patron que sale de lo que vio cumpla el estandar (rubrica
determinista: familia soportada, todos los talles simulados, documento sin
claves crudas, textura presente en el patron, categoria correcta).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from ai.config import AIConfig
from ai.extractor import extract_garment
from engine.document import build_document
from engine.garments import GarmentError, generate_size_set
from engine.spec import GarmentSpec, PatternParams
from engine.text import render_document_text
from render.pdf import render_document_pdf
from vision.preprocess import prepare_image

PHOTOS = Path(__file__).with_name("photos")
RESULTS = Path(__file__).with_name("results")
_KEY_LEAK = re.compile(r"\b(?:pattern|doc|schematic|warning|measure|title|section|desc)\.[a-z_.]+")
FIELDS = ("categoria", "tecnica", "construccion", "escote", "largo_manga", "punto_base")


def _value(spec: GarmentSpec, field: str) -> Any:
    value = getattr(spec, field)
    return value.value if hasattr(value, "value") else value


def field_scores(expected: dict[str, Any], spec: GarmentSpec) -> dict[str, bool]:
    """Acierto por campo esperado. Texturas: las esperadas deben aparecer."""
    scores: dict[str, bool] = {}
    for field, wanted in expected.items():
        if field == "texturas":
            seen = {t.textura.value for t in spec.texturas}
            scores[field] = set(wanted) <= seen and (bool(wanted) or not seen)
        elif field in FIELDS:
            scores[field] = _value(spec, field) == wanted
    return scores


def rubric(expected: dict[str, Any], spec: GarmentSpec) -> dict[str, bool]:
    """Rubrica determinista del patron que sale de `spec`."""
    checks = {
        "familia_soportada": False,
        "todos_los_talles_simulados": False,
        "documento_sin_claves": False,
        "textura_en_el_patron": not expected.get("texturas"),
        "categoria_correcta": spec.categoria.value == expected.get("categoria", spec.categoria.value),
        # "motivo": true en expected = la foto es un motivo radial a reproducir.
        "motivo_reproducido": not expected.get("motivo"),
    }
    try:
        patterns = generate_size_set(spec, PatternParams())
    except GarmentError:
        return checks
    checks["familia_soportada"] = True
    checks["todos_los_talles_simulados"] = True  # generate_size_set solo devuelve simulados
    document = build_document(patterns, highlight="M")
    text = render_document_text(document)
    checks["documento_sin_claves"] = not _KEY_LEAK.search(text) and render_document_pdf(document).startswith(b"%PDF")
    if expected.get("motivo"):
        checks["motivo_reproducido"] = patterns[0].meta.family == "crochet_motif"
    if expected.get("texturas"):
        checks["textura_en_el_patron"] = any("panel_rows" in s.meta for s in patterns[0].sections)
    return checks


async def run() -> dict[str, Any]:
    if os.environ.get("FAKE_AI") == "1" or not os.environ.get("AI_API_KEY"):
        raise SystemExit("eval-fotos necesita la IA real (AI_API_KEY y FAKE_AI=0).")
    cases = json.loads((PHOTOS / "cases.json").read_text(encoding="utf-8"))
    if not cases:
        raise SystemExit("No hay fotos en evals/photos/cases.json (ver evals/photos/README.md).")
    config = AIConfig.from_env()
    rows = []
    prompt_version = ""
    for case in cases:
        names = case.get("files") or [case["file"]]  # una o varias fotos de la pieza
        prepared = [prepare_image((PHOTOS / name).read_bytes()) for name in names]
        result = await extract_garment(prepared, config)
        prompt_version = result.prompt_version
        expected = case.get("expected", {})
        rows.append(
            {
                "id": case["id"],
                "campos": field_scores(expected, result.spec),
                "rubrica": rubric(expected, result.spec),
                "visto": result.spec.model_dump(mode="json", exclude={"confianza"}),
            }
        )
    return summarize(rows, prompt_version, config.model_extractor or config.model or "?")


def summarize(rows: list[dict[str, Any]], prompt_version: str, model: str) -> dict[str, Any]:
    def rate(kind: str) -> dict[str, float]:
        totals: dict[str, list[bool]] = {}
        for row in rows:
            for name, ok in row[kind].items():
                totals.setdefault(name, []).append(ok)
        return {name: sum(values) / len(values) for name, values in sorted(totals.items())}

    return {
        "fecha": date.today().isoformat(),
        "modelo": model,
        "prompt": prompt_version,
        "casos": len(rows),
        "precision_por_campo": rate("campos"),
        "rubrica": rate("rubrica"),
        "detalle": rows,
    }


def to_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Evaluación con fotos — {report['fecha']}",
        "",
        f"Modelo `{report['modelo']}` · prompt `{report['prompt']}` · {report['casos']} fotos",
        "",
        "| IA: campo | aciertos |",
        "| --- | --- |",
        *[f"| {k} | {v:.0%} |" for k, v in report["precision_por_campo"].items()],
        "",
        "| Patrón: criterio | cumple |",
        "| --- | --- |",
        *[f"| {k} | {v:.0%} |" for k, v in report["rubrica"].items()],
        "",
        "## Fallas",
        "",
    ]
    for row in report["detalle"]:
        failed = [k for k, ok in {**row["campos"], **row["rubrica"]}.items() if not ok]
        if failed:
            lines.append(f"- `{row['id']}`: {', '.join(failed)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    report = asyncio.run(run())
    RESULTS.mkdir(exist_ok=True)
    stem = RESULTS / f"{report['fecha']}-{report['prompt']}"
    stem.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    stem.with_suffix(".md").write_text(to_markdown(report), encoding="utf-8")
    print(to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
