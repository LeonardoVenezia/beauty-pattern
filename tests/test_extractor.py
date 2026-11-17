from __future__ import annotations

import json
from io import BytesIO

import pytest
from PIL import Image

from ai.config import AIConfig
from ai.errors import ExtractionError
from ai.extractor import build_messages, consolidate, extract_garment
from ai.fake import FakeAIClient
from ai.prompts.extractor_v4 import EXTRACTOR_SYSTEM_PROMPT, EXTRACTOR_USER_PROMPT
from ai.types import ImagePart
from vision.preprocess import prepare_image


def fake_config(samples: int = 3) -> AIConfig:
    return AIConfig(
        provider="fake",
        base_url=None,
        api_key=None,
        model="fake",
        fake=True,
        extractor_samples=samples,
    )


def prepared():
    buffer = BytesIO()
    Image.new("RGB", (300, 400), "white").save(buffer, format="PNG")
    return prepare_image(buffer.getvalue())


def payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "categoria": "pullover",
        "tecnica": "needles",
        "construccion": "raglan_top_down",
        "escote": "crew",
        "largo_cuerpo": "hip",
        "largo_manga": "long",
        "ajuste": "regular",
        "punto_base": "stockinette",
        "observaciones": "pullover liso",
    }
    data.update(overrides)
    return data


async def test_fake_extractor_is_deterministic_and_uses_images() -> None:
    image = prepared()
    config = fake_config(3)
    result = await extract_garment(image, config)
    assert result.spec.categoria.value == "pullover"
    assert result.spec.escote.value == "crew"
    assert result.spec.construccion.value == "raglan_top_down"
    assert result.confidence["categoria"] == 1.0
    assert len(result.samples) == 3
    assert result.prompt_version == "extractor-v5"
    assert result.usage.total_tokens == 0
    assert "espalda" in result.spec.no_visible


async def test_extractor_sends_main_image_and_crops() -> None:
    image = prepared()
    client = FakeAIClient(handler=lambda messages, model, response_format: json.dumps(payload()))
    await extract_garment(image, fake_config(1), client=client, samples=1)
    parts = [part for message in client.calls[0].messages for part in message.parts]
    images = [part for part in parts if isinstance(part, ImagePart)]
    assert len(images) == 1 + len(image.crops)


async def test_voting_marks_disagreements() -> None:
    image = prepared()
    responses = [
        json.dumps(payload(escote="crew")),
        json.dumps(payload(escote="crew")),
        json.dumps(payload(escote="v_neck")),
    ]
    client = FakeAIClient(responses=responses)
    result = await extract_garment(image, fake_config(3), client=client, samples=3)
    assert result.spec.escote.value == "crew"
    assert result.confidence["escote"] == pytest.approx(2 / 3)
    assert "escote" in result.disagreements
    assert any("escote" in item for item in result.spec.incertidumbres)


async def test_repair_retries_after_invalid_json() -> None:
    image = prepared()
    responses = ["no es json", json.dumps(payload(escote="boat"))]
    client = FakeAIClient(responses=responses)
    result = await extract_garment(image, fake_config(1), client=client, samples=1)
    assert result.spec.escote.value == "boat"
    assert len(client.calls) == 2


async def test_one_invalid_sample_does_not_discard_the_rest() -> None:
    image = prepared()
    responses = ["bad", "bad", "bad", json.dumps(payload(escote="boat"))]
    client = FakeAIClient(responses=responses)
    result = await extract_garment(image, fake_config(2), client=client, samples=2)
    assert result.spec.escote.value == "boat"
    assert len(result.samples) == 1


async def test_all_invalid_samples_fail_clearly() -> None:
    image = prepared()
    client = FakeAIClient(responses=["bad", "bad", "bad"])
    with pytest.raises(ExtractionError):
        await extract_garment(image, fake_config(1), client=client, samples=1)


def test_consolidate_rejects_empty_samples() -> None:
    with pytest.raises(ExtractionError):
        consolidate([])


def test_build_messages_includes_prompt_and_images() -> None:
    image = prepared()
    messages = build_messages(image)
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert any(isinstance(part, ImagePart) for part in messages[1].parts)


def test_prompt_distinguishes_bag_from_flat_square() -> None:
    assert "NO es un bolso" in EXTRACTOR_SYSTEM_PROMPT
    assert "granny_square" in EXTRACTOR_USER_PROMPT
    assert "asas o correas" in EXTRACTOR_SYSTEM_PROMPT


async def test_extractor_sends_every_photo_and_quality_notice() -> None:
    first, second = prepared(), prepared()
    client = FakeAIClient(handler=lambda messages, model, response_format: json.dumps(payload()))
    await extract_garment([first, second], fake_config(1), client=client, samples=1)
    parts = [part for message in client.calls[0].messages for part in message.parts]
    images = [part for part in parts if isinstance(part, ImagePart)]
    assert len(images) == 2 + len(first.crops)  # recortes solo de la foto 1
    text = " ".join(part.text for part in parts if hasattr(part, "text"))
    assert "Foto 2:" in text
    assert "Aviso de calidad" in text  # fondo blanco liso: desenfocada


def test_prompt_handles_imperfect_photos_and_any_knitting() -> None:
    assert "varias fotos" in EXTRACTOR_SYSTEM_PROMPT
    assert "imperfectas" in EXTRACTOR_SYSTEM_PROMPT
    assert "Cualquier tejido es valido" in EXTRACTOR_SYSTEM_PROMPT
