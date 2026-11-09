"""Aplicacion FastAPI.

Hito 1: salud del motor y sondeo de capacidades de la IA.
Los endpoints de analisis y patron se agregan en los hitos siguientes.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai.config import AIConfig
from ai.errors import AIConfigError
from ai.probe import CapabilityProbe
from engine import ENGINE_VERSION

app = FastAPI(title="Tejedora API", version=ENGINE_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "engine_version": ENGINE_VERSION}


@app.get("/health/ai")
async def health_ai(refresh: bool = False) -> dict[str, object]:
    try:
        config = AIConfig.from_env()
    except AIConfigError as exc:
        return {
            "configured": False,
            "error": str(exc),
            "hint": "Defini AI_BASE_URL, AI_API_KEY y AI_MODEL, o usa FAKE_AI=1.",
        }
    probe = CapabilityProbe(config)
    try:
        capabilities = await probe.run(force=refresh)
    finally:
        await probe.aclose()
    return {"configured": True, **capabilities.model_dump()}
