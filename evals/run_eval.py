"""Evaluacion del extractor por campo, con reporte por version de prompt.

Uso:
    make eval                 # usa FAKE_AI=1 si no hay clave configurada
    FAKE_AI=0 make eval       # usa el endpoint real si hay AI_API_KEY

Las imagenes de `evals/` son sinteticas por ahora (ver `evals/images.py`).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from ai.config import AIConfig
from ai.errors import AIConfigError
from ai.extractor import extract_garment
from evals.images import synthetic_case_image
from vision.preprocess import prepare_image

CASES_PATH = Path(__file__).with_name("cases.json")


def _value(spec: Any, field: str) -> Any:
    value = getattr(spec, field)
    if hasattr(value, "value"):
        return value.value
    return value


def _prepare_env() -> None:
    if not os.environ.get("FAKE_AI") and not os.environ.get("AI_API_KEY"):
        os.environ["FAKE_AI"] = "1"


async def run() -> dict[str, Any]:
    _prepare_env()
    config = AIConfig.from_env()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    field_hits: dict[str, int] = {}
    field_total: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    prompt_version = ""
    for case in cases:
        image_bytes = synthetic_case_image(int(case.get("seed", 1)))
        prepared = prepare_image(image_bytes)
        result = await extract_garment(prepared, config)
        prompt_version = result.prompt_version
        expected = case.get("expected", {})
        row: dict[str, Any] = {"id": case["id"], "fields": {}}
        for field, expected_value in expected.items():
            actual = _value(result.spec, field)
            hit = actual == expected_value
            field_hits[field] = field_hits.get(field, 0) + int(hit)
            field_total[field] = field_total.get(field, 0) + 1
            row["fields"][field] = {
                "expected": expected_value,
                "actual": actual,
                "ok": hit,
            }
        rows.append(row)
    accuracy = {
        field: field_hits[field] / field_total[field]
        for field in sorted(field_total)
    }
    overall = (
        sum(field_hits.values()) / sum(field_total.values())
        if field_total
        else 0.0
    )
    return {
        "mode": "fake" if config.fake else "real",
        "prompt_version": prompt_version,
        "cases": len(cases),
        "field_accuracy": accuracy,
        "overall_accuracy": overall,
        "details": rows,
    }


def main() -> int:
    try:
        report = asyncio.run(run())
    except AIConfigError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
