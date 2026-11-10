from __future__ import annotations

from ai.prompts.extractor_v1 import EXTRACTOR_PROMPT_VERSION, extractor_response_format
from evals.run_eval import run


async def test_fake_eval_reports_per_field_accuracy(monkeypatch) -> None:
    monkeypatch.setenv("FAKE_AI", "1")
    report = await run()
    assert report["mode"] == "fake"
    assert report["prompt_version"] == EXTRACTOR_PROMPT_VERSION
    assert report["cases"] == 3
    assert report["overall_accuracy"] == 1.0
    assert report["field_accuracy"]["categoria"] == 1.0


def test_extractor_response_format_contains_garment_schema() -> None:
    response_format = extractor_response_format()
    assert response_format["type"] == "json_schema"
    schema = response_format["json_schema"]["schema"]
    assert "categoria" in schema["properties"]
    assert "confianza" in schema["properties"]
