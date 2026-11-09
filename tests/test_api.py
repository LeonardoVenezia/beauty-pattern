from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


def test_health(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "engine_version" in response.json()


def test_health_ai_fake(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setenv("FAKE_AI", "1")
    monkeypatch.setenv("AI_CACHE_DIR", str(tmp_path))
    with TestClient(app) as client:
        response = client.get("/health/ai")
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["fake"] is True
    assert data["images"] is True


def test_health_ai_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "FAKE_AI",
        "AI_MODEL",
        "AI_BASE_URL",
        "AI_API_KEY",
        "AI_MODEL_EXTRACTOR",
        "AI_MODEL_WRITER",
        "AI_MODEL_CRITIC",
    ):
        monkeypatch.delenv(name, raising=False)
    with TestClient(app) as client:
        response = client.get("/health/ai")
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is False
    assert "error" in data
