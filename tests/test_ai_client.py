from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ai.client import OpenAICompatibleClient, ResponseCache, cache_key
from ai.config import AIConfig
from ai.errors import AIConfigError, AIError
from ai.fake import FakeAIClient, messages_text
from ai.types import ImagePart, Message, TextPart


def make_config(tmp_path: Path, **overrides: object) -> AIConfig:
    values: dict[str, object] = {
        "provider": "test",
        "base_url": "https://example.test/v1",
        "api_key": "secret-key",
        "model": "test-model",
        "cache_dir": tmp_path,
        "max_retries": 1,
        "price_input_per_mtok": 0.01,
        "price_output_per_mtok": 0.08,
    }
    values.update(overrides)
    return AIConfig(**values)  # type: ignore[arg-type]


def test_config_requires_endpoint_when_real() -> None:
    with pytest.raises(AIConfigError):
        AIConfig.from_env({})
    with pytest.raises(AIConfigError):
        AIConfig.from_env({"AI_MODEL": "m", "AI_API_KEY": "k"})
    with pytest.raises(AIConfigError):
        AIConfig.from_env({"AI_MODEL": "m", "AI_BASE_URL": "u"})


def test_config_fake_mode() -> None:
    config = AIConfig.from_env({"FAKE_AI": "1"})
    assert config.fake is True
    assert config.model_for("extractor") == "fake"
    assert config.require_endpoint() == ("fake", "fake", "fake")


def test_config_role_models() -> None:
    config = AIConfig.from_env(
        {
            "AI_MODEL": "base",
            "AI_BASE_URL": "https://example.test/v1",
            "AI_API_KEY": "k",
            "AI_MODEL_EXTRACTOR": "vision",
            "AI_MODEL_WRITER": "writer",
        }
    )
    assert config.model_for("extractor") == "vision"
    assert config.model_for("writer") == "writer"
    assert config.model_for("critic") == "base"


@pytest.mark.asyncio
async def test_fake_client_queue_and_calls() -> None:
    client = FakeAIClient(responses=['{"a": 1}', '{"a": 2}'])
    first = await client.complete([Message.user_text("hola")])
    second = await client.complete([Message.user_text("hola")])
    assert first.text == '{"a": 1}'
    assert second.text == '{"a": 2}'
    assert len(client.calls) == 2
    assert messages_text(client.calls[0].messages) == "hola"
    await client.aclose()


def test_cache_key_depends_on_image_and_prompt() -> None:
    message = Message(
        role="user",
        parts=(TextPart("describe"), ImagePart(b"abc", "image/png")),
    )
    base = dict(model="m", response_format=None, temperature=0.2, max_tokens=10)
    key1 = cache_key([message], **base)  # type: ignore[arg-type]
    key2 = cache_key([message], **base)  # type: ignore[arg-type]
    assert key1 == key2
    other = Message(role="user", parts=(TextPart("otra cosa"), ImagePart(b"abc", "image/png")))
    assert cache_key([other], **base) != key1  # type: ignore[arg-type]
    other_image = Message(role="user", parts=(TextPart("describe"), ImagePart(b"xyz", "image/png")))
    assert cache_key([other_image], **base) != key1  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_openai_client_request_and_usage(tmp_path: Path) -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-key"
        assert str(request.url) == "https://example.test/v1/chat/completions"
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 500,
                    "total_tokens": 1500,
                },
            },
        )

    config = make_config(tmp_path)
    client = OpenAICompatibleClient(config, transport=httpx.MockTransport(handler))
    response = await client.complete([Message.user_text("hola")], max_tokens=32)
    assert response.text == "ok"
    assert response.usage.prompt_tokens == 1000
    assert response.usage.completion_tokens == 500
    assert response.usage.cost_usd == pytest.approx(0.00005)
    assert requests[0]["model"] == "test-model"
    assert requests[0]["max_tokens"] == 32
    assert (tmp_path / "usage.jsonl").exists()
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_client_sends_images_as_data_url(tmp_path: Path) -> None:
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": {}},
        )

    config = make_config(tmp_path)
    client = OpenAICompatibleClient(config, transport=httpx.MockTransport(handler))
    message = Message(
        role="user",
        parts=(TextPart("que es"), ImagePart(b"\x89PNG", "image/png")),
    )
    await client.complete([message])
    content = captured[0]["messages"][0]["content"]  # type: ignore[index]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "que es"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_client_caches(tmp_path: Path) -> None:
    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "cacheado"}}], "usage": {}},
        )

    config = make_config(tmp_path)
    client = OpenAICompatibleClient(config, transport=httpx.MockTransport(handler))
    first = await client.complete([Message.user_text("igual")])
    second = await client.complete([Message.user_text("igual")])
    assert count == 1
    assert first.text == second.text == "cacheado"
    assert second.cached is True
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_client_retries_429(tmp_path: Path) -> None:
    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        if count == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, text="busy")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": {}},
        )

    config = make_config(tmp_path, max_retries=1)
    client = OpenAICompatibleClient(config, transport=httpx.MockTransport(handler))
    response = await client.complete([Message.user_text("reintenta")])
    assert response.text == "ok"
    assert count == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_client_does_not_retry_401(tmp_path: Path) -> None:
    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(401, text="bad key")

    config = make_config(tmp_path, max_retries=2)
    client = OpenAICompatibleClient(config, transport=httpx.MockTransport(handler))
    with pytest.raises(AIError):
        await client.complete([Message.user_text("no")])
    assert count == 1
    await client.aclose()


def test_response_cache_roundtrip(tmp_path: Path) -> None:
    from ai.types import AIResponse, Usage

    cache = ResponseCache(tmp_path)
    assert cache.get("abc") is None
    cache.set("abc", AIResponse(text="hola", model="m", usage=Usage(prompt_tokens=1)))
    got = cache.get("abc")
    assert got is not None
    assert got.text == "hola"
    assert got.cached is True
