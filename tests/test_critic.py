from __future__ import annotations

import json
from io import BytesIO

from PIL import Image

from ai.config import AIConfig
from ai.critic import critique_pattern
from ai.fake import FakeAIClient
from engine.garments import generate
from engine.spec import Category, Construction, GarmentSpec, PatternParams, Technique
from vision.preprocess import prepare_image


def fake_config() -> AIConfig:
    return AIConfig(
        provider="fake",
        base_url=None,
        api_key=None,
        model="fake",
        fake=True,
    )


def prepared():
    buffer = BytesIO()
    Image.new("RGB", (300, 400), "white").save(buffer, format="PNG")
    return prepare_image(buffer.getvalue())


def pattern():
    return generate(
        GarmentSpec(
            categoria=Category.PULLOVER,
            tecnica=Technique.CIRCULAR,
            construccion=Construction.RAGLAN_TOP_DOWN,
        ),
        PatternParams(talla="M"),
    )


async def test_fake_critic_returns_informative_warnings() -> None:
    garment = pattern()
    result = await critique_pattern(
        prepared(), garment.spec, garment, config=fake_config()
    )
    assert result.fallback_used is False
    assert result.observations
    assert result.risks
    assert result.prompt_version == "critic-v1"


async def test_critic_repairs_invalid_json() -> None:
    garment = pattern()
    valid = json.dumps({"observaciones": ["revisar manga"], "riesgos": []})
    client = FakeAIClient(responses=["esto no es json", valid])
    result = await critique_pattern(
        prepared(), garment.spec, garment, config=fake_config(), client=client
    )
    assert result.fallback_used is False
    assert result.observations == ("revisar manga",)
    assert len(client.calls) == 2


async def test_critic_falls_back_after_invalid_responses() -> None:
    garment = pattern()
    client = FakeAIClient(responses=["no json", "tampoco"])
    result = await critique_pattern(
        prepared(), garment.spec, garment, config=fake_config(), client=client
    )
    assert result.fallback_used is True
    assert result.observations == ()
    assert result.risks == ()
