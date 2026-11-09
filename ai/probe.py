"""Sondeo de capacidades del endpoint de IA.

Prueba, con llamadas reales y acotadas:
1. texto;
2. entrada de imagenes (con una imagen sintetica que dice "42");
3. salida JSON estructurada (`response_format` json_schema y json_object);
4. tool calling (opcional, informativo).

El resultado se cachea y se expone en `GET /health/ai`. Con FAKE_AI=1 no se
hace ninguna llamada: se devuelve un resultado marcado como falso.
"""

from __future__ import annotations

import io
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

from ai.client import AIClient, OpenAICompatibleClient
from ai.config import AIConfig
from ai.errors import AIError
from ai.types import ImagePart, Message, TextPart

CACHE_TTL = timedelta(hours=24)


class Capabilities(BaseModel):
    provider: str
    model: str
    fake: bool = False
    text: bool = False
    images: bool = False
    images_verified: bool = False
    json_schema: bool = False
    json_object: bool = False
    tools: bool = False
    checked_at: str
    latency_ms: dict[str, float] = Field(default_factory=dict)
    details: dict[str, str] = Field(default_factory=dict)


def synthetic_number_image(number: str = "42") -> bytes:
    image = Image.new("RGB", (128, 128), "white")
    draw = ImageDraw.Draw(image)
    draw.text((28, 34), number, fill="black", font_size=64)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def _timed(coro: Any) -> tuple[Any, float]:
    started = time.perf_counter()
    result = await coro
    return result, (time.perf_counter() - started) * 1000


class CapabilityProbe:
    def __init__(self, config: AIConfig, client: AIClient | None = None) -> None:
        self._config = config
        self._client = client
        self._owns_client = client is None and not config.fake
        self._cache_path = config.cache_dir / "capabilities.json"

    def _get_client(self) -> AIClient:
        if self._client is None:
            if self._config.fake:
                raise RuntimeError("no hay cliente real en modo FAKE_AI")
            self._client = OpenAICompatibleClient(self._config)
        return self._client

    def _read_cache(self) -> Capabilities | None:
        if not self._cache_path.exists():
            return None
        try:
            capabilities = Capabilities.model_validate_json(
                self._cache_path.read_text(encoding="utf-8")
            )
            checked = datetime.fromisoformat(capabilities.checked_at)
            if datetime.now(UTC) - checked > CACHE_TTL:
                return None
            return capabilities
        except (OSError, ValueError):
            return None

    def _write_cache(self, capabilities: Capabilities) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(
            capabilities.model_dump_json(indent=2), encoding="utf-8"
        )

    def cached(self) -> Capabilities | None:
        return self._read_cache()

    async def run(self, *, force: bool = False) -> Capabilities:
        if self._config.fake:
            return Capabilities(
                provider="fake",
                model="fake",
                fake=True,
                text=True,
                images=True,
                images_verified=True,
                json_schema=True,
                json_object=True,
                tools=True,
                checked_at=datetime.now(UTC).isoformat(),
                details={"mode": "FAKE_AI=1 (sin llamadas de red)"},
            )
        if not force:
            cached = self._read_cache()
            if cached is not None:
                return cached

        client = self._get_client()
        capabilities = Capabilities(
            provider=self._config.provider,
            model=self._config.model_for("extractor"),
            checked_at=datetime.now(UTC).isoformat(),
        )

        # 1. Texto
        try:
            response, latency = await _timed(
                client.complete(
                    [Message.user_text("Reply with the single word: ok")],
                    model=capabilities.model,
                    temperature=0.0,
                    max_tokens=8,
                )
            )
            capabilities.text = bool(response.text.strip())
            capabilities.latency_ms["text"] = round(latency, 1)
        except AIError as exc:
            capabilities.details["text"] = str(exc)[:300]

        # 2. Imagenes: pedir que lea un numero conocido.
        try:
            response, latency = await _timed(
                client.complete(
                    [
                        Message(
                            role="user",
                            parts=(
                                TextPart(
                                    "Read the number in the image. Answer with digits only."
                                ),
                                ImagePart(synthetic_number_image(), "image/png"),
                            ),
                        )
                    ],
                    model=capabilities.model,
                    temperature=0.0,
                    max_tokens=8,
                )
            )
            capabilities.images = bool(response.text.strip())
            capabilities.images_verified = "42" in response.text
            capabilities.latency_ms["images"] = round(latency, 1)
            capabilities.details["images_answer"] = response.text.strip()[:80]
        except AIError as exc:
            capabilities.images = False
            capabilities.details["images"] = str(exc)[:300]

        # 3a. JSON schema
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        }
        try:
            response, latency = await _timed(
                client.complete(
                    [Message.user_text('Return JSON with the key "ok" set to true.')],
                    model=capabilities.model,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "probe",
                            "strict": True,
                            "schema": schema,
                        },
                    },
                    temperature=0.0,
                    max_tokens=32,
                )
            )
            json.loads(response.text)
            capabilities.json_schema = True
            capabilities.latency_ms["json_schema"] = round(latency, 1)
        except (AIError, ValueError) as exc:
            capabilities.details["json_schema"] = str(exc)[:300]

        # 3b. JSON object (plan B)
        try:
            response, latency = await _timed(
                client.complete(
                    [Message.user_text('Return only this JSON: {"ok": true}')],
                    model=capabilities.model,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=32,
                )
            )
            json.loads(response.text)
            capabilities.json_object = True
            capabilities.latency_ms["json_object"] = round(latency, 1)
        except (AIError, ValueError) as exc:
            capabilities.details["json_object"] = str(exc)[:300]

        # 4. Tool calling (opcional)
        try:
            response, latency = await _timed(
                client.complete(
                    [Message.user_text("Call the ping tool with value 1.")],
                    model=capabilities.model,
                    temperature=0.0,
                    max_tokens=64,
                    extra={
                        "tools": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "ping",
                                    "description": "Ping the server.",
                                    "parameters": {
                                        "type": "object",
                                        "properties": {"value": {"type": "integer"}},
                                        "required": ["value"],
                                    },
                                },
                            }
                        ],
                        "tool_choice": "auto",
                    },
                )
            )
            capabilities.tools = bool(response.tool_calls)
            capabilities.latency_ms["tools"] = round(latency, 1)
        except AIError as exc:
            capabilities.details["tools"] = str(exc)[:300]

        self._write_cache(capabilities)
        return capabilities

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()


def capabilities_path(config: AIConfig) -> Path:
    return config.cache_dir / "capabilities.json"
