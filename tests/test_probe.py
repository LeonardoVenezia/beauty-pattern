from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from ai.config import AIConfig
from ai.probe import CapabilityProbe, synthetic_number_image
from ai.types import AIResponse, ImagePart, Message


class StubVisionClient:
    def __init__(self) -> None:
        self.calls = 0

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
        self.calls += 1
        if extra and "tools" in extra:
            return AIResponse(
                text="",
                model="m",
                tool_calls=({"id": "1", "type": "function", "function": {"name": "ping"}},),
            )
        if response_format is not None:
            return AIResponse(text='{"ok": true}', model="m")
        has_image = any(
            isinstance(part, ImagePart) for message in messages for part in message.parts
        )
        if has_image:
            return AIResponse(text="42", model="m")
        return AIResponse(text="ok", model="m")

    async def aclose(self) -> None:
        return None


def real_config(tmp_path: Path) -> AIConfig:
    return AIConfig(
        provider="test",
        base_url="https://example.test/v1",
        api_key="k",
        model="test-model",
        cache_dir=tmp_path,
    )


@pytest.mark.asyncio
async def test_fake_probe_does_not_call_network(tmp_path: Path) -> None:
    config = AIConfig.from_env({"FAKE_AI": "1", "AI_CACHE_DIR": str(tmp_path)})
    probe = CapabilityProbe(config)
    capabilities = await probe.run()
    assert capabilities.fake is True
    assert capabilities.text and capabilities.images and capabilities.json_schema
    assert capabilities.images_verified is True
    await probe.aclose()


@pytest.mark.asyncio
async def test_real_probe_with_stub(tmp_path: Path) -> None:
    client = StubVisionClient()
    probe = CapabilityProbe(real_config(tmp_path), client=client)
    capabilities = await probe.run()
    assert capabilities.text is True
    assert capabilities.images is True
    assert capabilities.images_verified is True
    assert capabilities.json_schema is True
    assert capabilities.json_object is True
    assert capabilities.tools is True
    assert capabilities.details["images_answer"] == "42"
    assert client.calls == 5
    cached = probe.cached()
    assert cached is not None
    assert cached.model == "test-model"
    # La segunda corrida usa cache y no vuelve a llamar.
    again = await probe.run()
    assert again.checked_at == capabilities.checked_at
    assert client.calls == 5
    await probe.aclose()


def test_synthetic_image_is_png() -> None:
    data = synthetic_number_image()
    assert data.startswith(b"\x89PNG")
