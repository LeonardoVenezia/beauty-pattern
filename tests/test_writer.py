from __future__ import annotations

from ai.config import AIConfig
from ai.fake import FakeAIClient
from ai.writer import (
    allowed_numbers,
    extract_numbers,
    unknown_numbers,
    write_pattern_text,
)
from engine.garments import generate
from engine.spec import Category, Construction, GarmentSpec, PatternParams, Technique
from engine.text import render_pattern_text


def fake_config() -> AIConfig:
    return AIConfig(
        provider="fake",
        base_url=None,
        api_key=None,
        model="fake",
        fake=True,
    )


def pattern():
    return generate(
        GarmentSpec(
            categoria=Category.PULLOVER,
            tecnica=Technique.CIRCULAR,
            construccion=Construction.RAGLAN_TOP_DOWN,
        ),
        PatternParams(talla="M"),
    )


def test_extract_numbers_accepts_decimal_comma() -> None:
    assert extract_numbers("22,5 cm y 30 puntos") == [22.5, 30.0]


def test_allowed_numbers_include_ir_counts() -> None:
    allowed = allowed_numbers(pattern(), "es")
    assert 80.0 in allowed
    assert 328.0 in allowed
    assert 220.0 in allowed


async def test_fake_writer_returns_canonical_text() -> None:
    garment = pattern()
    result = await write_pattern_text(garment, config=fake_config())
    assert result.fallback_used is False
    assert result.text == render_pattern_text(garment, lang="es")
    assert result.attempts == 1
    assert result.validation_errors == ()


async def test_writer_repairs_hallucinated_number() -> None:
    garment = pattern()
    canonical = render_pattern_text(garment, lang="es")
    client = FakeAIClient(responses=["Montar 999 puntos.", canonical])
    result = await write_pattern_text(
        garment, config=fake_config(), client=client, max_attempts=2
    )
    assert result.fallback_used is False
    assert result.attempts == 2
    assert result.text == canonical
    assert "999" in result.validation_errors[0]


async def test_writer_falls_back_when_numbers_keep_failing() -> None:
    garment = pattern()
    client = FakeAIClient(responses=["Montar 999 puntos.", "Tejer 777 vueltas."])
    result = await write_pattern_text(
        garment, config=fake_config(), client=client, max_attempts=2
    )
    assert result.fallback_used is True
    assert result.text == render_pattern_text(garment, lang="es")
    assert len(result.validation_errors) == 2


def test_unknown_numbers_are_sorted() -> None:
    assert unknown_numbers("80 y 999 y 12,5", {80.0, 12.5}) == [999.0]


async def test_writer_language_changes_canonical() -> None:
    garment = pattern()
    result = await write_pattern_text(garment, language="en", config=fake_config())
    assert "size" in result.text.lower()
