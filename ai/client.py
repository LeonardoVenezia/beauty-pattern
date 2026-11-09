"""Cliente de IA compatible con OpenAI Chat Completions.

Refuseless documenta esta forma exacta (2026-11-09): POST a
`{AI_BASE_URL}/chat/completions`, header `Authorization: Bearer ...`,
mensajes OpenAI y `response_format` pasado tal cual. La URL y el modelo
vienen solo del entorno.

Incluye cache por hash de prompt + imagen, reintentos acotados y registro de
tokens/costo. Nunca registra la clave.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

from ai.config import AIConfig
from ai.errors import AIError, AIResponseError
from ai.types import AIResponse, ImagePart, Message, TextPart, Usage

_RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class AIClient(Protocol):
    async def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AIResponse: ...

    async def aclose(self) -> None: ...


def _message_fingerprint(messages: Sequence[Message]) -> list[Any]:
    fingerprint: list[Any] = []
    for message in messages:
        parts: list[Any] = []
        for part in message.parts:
            if isinstance(part, TextPart):
                parts.append(["text", part.text])
            elif isinstance(part, ImagePart):
                parts.append(
                    ["image", hashlib.sha256(part.data).hexdigest(), part.mime_type]
                )
            else:  # pragma: no cover - tipo cerrado
                raise TypeError(f"parte de mensaje desconocida: {part!r}")
        fingerprint.append([message.role, parts])
    return fingerprint


def cache_key(
    messages: Sequence[Message],
    *,
    model: str,
    response_format: dict[str, Any] | None,
    temperature: float,
    max_tokens: int | None,
    extra: dict[str, Any] | None = None,
) -> str:
    payload = {
        "model": model,
        "messages": _message_fingerprint(messages),
        "response_format": response_format,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "extra": extra,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _openai_content(parts: Sequence[TextPart | ImagePart]) -> str | list[dict[str, Any]]:
    if len(parts) == 1 and isinstance(parts[0], TextPart):
        return parts[0].text
    content: list[dict[str, Any]] = []
    for part in parts:
        if isinstance(part, TextPart):
            content.append({"type": "text", "text": part.text})
        else:
            encoded = base64.b64encode(part.data).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{part.mime_type};base64,{encoded}"},
                }
            )
    return content


def _openai_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
    return [
        {"role": message.role, "content": _openai_content(message.parts)}
        for message in messages
    ]


def _extract_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
        return "".join(chunks)
    if content is None:
        return ""
    return str(content)


def _parse_usage(data: dict[str, Any], config: AIConfig) -> Usage:
    usage = data.get("usage") or {}
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(
        usage.get("completion_tokens") or usage.get("output_tokens") or 0
    )
    total = int(usage.get("total_tokens") or prompt + completion)
    cost = (
        prompt / 1_000_000 * config.price_input_per_mtok
        + completion / 1_000_000 * config.price_output_per_mtok
    )
    return Usage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        cost_usd=round(cost, 8),
    )


class ResponseCache:
    def __init__(self, directory: Path) -> None:
        self._directory = directory / "responses"
        self._directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._directory / f"{key}.json"

    def get(self, key: str) -> AIResponse | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            usage = Usage(**data.get("usage", {}))
            return AIResponse(
                text=data["text"],
                model=data["model"],
                usage=usage,
                cached=True,
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def set(self, key: str, response: AIResponse) -> None:
        path = self._path(key)
        payload = {
            "text": response.text,
            "model": response.model,
            "usage": asdict(response.usage),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)


class UsageLog:
    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self._path = directory / "usage.jsonl"
        self._lock = asyncio.Lock()

    async def record(
        self,
        *,
        model: str,
        usage: Usage,
        latency_ms: float,
        prompt_hash: str,
        cached: bool,
    ) -> None:
        entry = {
            "at": datetime.now(UTC).isoformat(),
            "model": model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cost_usd": usage.cost_usd,
            "latency_ms": round(latency_ms, 1),
            "prompt_sha256": prompt_hash,
            "cached": cached,
        }
        async with self._lock:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


class OpenAICompatibleClient:
    def __init__(self, config: AIConfig, transport: httpx.AsyncBaseTransport | None = None):
        self._config = config
        base_url, api_key, _ = config.require_endpoint()
        self._endpoint = base_url.rstrip("/") + "/chat/completions"
        self._client = httpx.AsyncClient(
            timeout=config.timeout_s,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            transport=transport,
        )
        self._cache = ResponseCache(config.cache_dir)
        self._usage = UsageLog(config.cache_dir)

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AIResponse:
        chosen_model = model or self._config.model_for("extractor")
        key = cache_key(
            messages,
            model=chosen_model,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra,
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        body: dict[str, Any] = {
            "model": chosen_model,
            "messages": _openai_messages(messages),
            "temperature": temperature,
        }
        if response_format is not None:
            body["response_format"] = response_format
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if extra:
            body.update(extra)

        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                response = await self._client.post(self._endpoint, json=body)
                if response.status_code in _RETRY_STATUS:
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                if response.status_code >= 400:
                    detail = response.text[:500]
                    raise AIError(
                        f"la IA respondio HTTP {response.status_code}: {detail}"
                    )
                data = response.json()
                choice = (data.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                text = _extract_text(message)
                tool_calls = tuple(message.get("tool_calls") or ())
                if not text.strip() and not tool_calls:
                    raise AIResponseError("la respuesta de la IA no tiene texto")
                usage = _parse_usage(data, self._config)
                latency_ms = (time.perf_counter() - started) * 1000
                result = AIResponse(
                    text=text,
                    model=str(data.get("model") or chosen_model),
                    usage=usage,
                    latency_ms=latency_ms,
                    tool_calls=tool_calls,
                )
                self._cache.set(key, result)
                await self._usage.record(
                    model=result.model,
                    usage=usage,
                    latency_ms=latency_ms,
                    prompt_hash=key,
                    cached=False,
                )
                return result
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error = exc
                if attempt >= self._config.max_retries:
                    break
                retry_after = 0.0
                if isinstance(exc, httpx.HTTPStatusError):
                    header = exc.response.headers.get("retry-after")
                    if header:
                        try:
                            retry_after = min(float(header), 5.0)
                        except ValueError:
                            retry_after = 0.0
                await asyncio.sleep(retry_after or min(0.5 * 2**attempt, 4.0))
        raise AIError(f"la llamada a la IA fallo: {last_error}") from last_error

    async def aclose(self) -> None:
        await self._client.aclose()
