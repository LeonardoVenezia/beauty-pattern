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


def _png() -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (320, 400), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _fake_env(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setenv("FAKE_AI", "1")
    monkeypatch.setenv("AI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "100")


def test_analyze_pattern_pdf_and_svg_flow(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    _fake_env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        analyzed = client.post(
            "/analyze", files={"file": ("sweater.png", _png(), "image/png")}
        )
        assert analyzed.status_code == 200, analyzed.text
        data = analyzed.json()
        assert data["spec"]["categoria"] == "pullover"
        assert data["image_id"]
        created = client.post(
            "/pattern",
            json={"spec": data["spec"], "params": {"talla": "M"}},
        )
        assert created.status_code == 200, created.text
        pattern = created.json()
        assert pattern["simulation"]["ok"] is True
        assert pattern["text"]["es"]
        assert pattern["text"]["en"]
        pattern_id = pattern["id"]

        fetched = client.get(f"/pattern/{pattern_id}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == pattern_id

        pdf = client.get(f"/pattern/{pattern_id}/pdf")
        assert pdf.status_code == 200
        assert pdf.content.startswith(b"%PDF")

        svg = client.get(f"/pattern/{pattern_id}/svg")
        assert svg.status_code == 200
        assert "<svg" in svg.text

        rewritten = client.post(
            f"/pattern/{pattern_id}/rewrite", json={"lang": "es"}
        )
        assert rewritten.status_code == 200, rewritten.text
        assert rewritten.json()["text"]
        assert rewritten.json()["fallback_used"] is False

        critique = client.post(
            f"/pattern/{pattern_id}/critique",
            json={"image_id": data["image_id"], "lang": "es"},
        )
        assert critique.status_code == 200, critique.text
        assert critique.json()["observations"]

        stitches = client.get("/stitches")
        assert stitches.status_code == 200
        assert any(item["id"] == "stockinette" for item in stitches.json())


def test_analyze_rejects_invalid_image(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    _fake_env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/analyze", files={"file": ("bad.png", b"not an image", "image/png")}
        )
    assert response.status_code == 422


def test_pattern_rejects_impossible_variant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    _fake_env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/pattern",
            json={
                "spec": {
                    "categoria": "pullover",
                    "tecnica": "needles",
                    "construccion": "raglan_top_down",
                    "largo_manga": "sleeveless",
                },
                "params": {"talla": "M"},
            },
        )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "error.unsupported_sleeve"


def test_pattern_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    _fake_env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert client.get("/pattern/nope/pdf").status_code == 404


def test_analyze_rate_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    _fake_env(monkeypatch, tmp_path)
    from api.main import limiter
    from api.ratelimit import RateLimiter

    monkeypatch.setattr("api.main.limiter", RateLimiter(1))
    with TestClient(app) as client:
        first = client.post(
            "/analyze", files={"file": ("sweater.png", _png(), "image/png")}
        )
        second = client.post(
            "/analyze", files={"file": ("sweater.png", _png(), "image/png")}
        )
    assert first.status_code == 200
    assert second.status_code == 429
    limiter.reset()
