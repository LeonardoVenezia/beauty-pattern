"""Redactor de patrones con validacion determinista de numeros.

La IA puede reescribir el texto, pero no cambiar ningun numero. Si la salida
contiene un numero que no aparece en el patron canonico, se repara o se usa la
plantilla determinista. La plantilla siempre existe y es la red de seguridad.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai.client import AIClient, OpenAICompatibleClient
from ai.config import AIConfig
from ai.errors import AIError
from ai.fake import FakeAIClient
from ai.prompts.writer_v1 import (
    WRITER_PROMPT_VERSION,
    WRITER_REPAIR_PROMPT,
    WRITER_SYSTEM_PROMPT,
    WRITER_USER_PROMPT,
)
from ai.types import AIResponse, Message, Usage
from engine.ir import Op, Pattern, Repeat, Section, Step
from engine.text import render_pattern_text

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def extract_numbers(text: str) -> list[float]:
    """Extrae numeros del texto, aceptando coma decimal."""
    values: list[float] = []
    for token in _NUMBER_RE.findall(text):
        try:
            values.append(float(token.replace(",", ".")))
        except ValueError:
            continue
    return values


def _normalize(value: float) -> float:
    return round(value, 4)


def _add_step_numbers(numbers: set[float], step: Step) -> None:
    numbers.add(_normalize(float(step.number)))
    numbers.add(_normalize(float(step.stitch_count_end)))
    for item in step.items:
        if isinstance(item, Op):
            numbers.add(_normalize(float(item.times)))
            if item.width is not None:
                numbers.add(_normalize(float(item.width)))
        else:
            repeat = item
            assert isinstance(repeat, Repeat)
            numbers.add(_normalize(float(repeat.times)))
            for op in repeat.ops:
                numbers.add(_normalize(float(op.times)))
                if op.width is not None:
                    numbers.add(_normalize(float(op.width)))


def _add_section_numbers(numbers: set[float], section: Section) -> None:
    numbers.add(_normalize(float(section.start_stitches)))
    numbers.add(_normalize(float(section.end_stitches)))
    for value in section.meta.values():
        numbers.add(_normalize(float(value)))
    if section.target is not None:
        numbers.add(_normalize(section.target.target_cm))
        numbers.add(_normalize(section.target.tolerance_cm))
    for step in section.steps:
        _add_step_numbers(numbers, step)


def allowed_numbers(pattern: Pattern, language: str | None = None) -> set[float]:
    """Numeros que el redactor puede usar: texto canonico + IR completa."""
    canonical = render_pattern_text(pattern, lang=language)
    numbers = {_normalize(value) for value in extract_numbers(canonical)}
    for measurement in pattern.measurements:
        numbers.add(_normalize(measurement.value_cm))
        if measurement.target_cm is not None:
            numbers.add(_normalize(measurement.target_cm))
        numbers.add(_normalize(measurement.tolerance_cm))
    for section in pattern.sections:
        _add_section_numbers(numbers, section)
    materials = pattern.materials
    numbers.add(_normalize(materials.meters))
    if materials.grams is not None:
        numbers.add(_normalize(materials.grams))
    if materials.needle_mm is not None:
        numbers.add(_normalize(materials.needle_mm))
    if materials.hook_mm is not None:
        numbers.add(_normalize(materials.hook_mm))
    if pattern.params.densidad is not None:
        numbers.add(_normalize(pattern.params.densidad.stitches_per_10cm))
        numbers.add(_normalize(pattern.params.densidad.rows_per_10cm))
    if pattern.params.ease_cm is not None:
        numbers.add(_normalize(pattern.params.ease_cm))
    if pattern.spec.colorwork is not None:
        numbers.add(_normalize(float(pattern.spec.colorwork.colores)))
    return numbers


def unknown_numbers(text: str, allowed: set[float]) -> list[float]:
    return sorted(
        {
            _normalize(value)
            for value in extract_numbers(text)
            if _normalize(value) not in allowed
        }
    )


def _summary(pattern: Pattern) -> str:
    return (
        f"Secciones: {', '.join(section.id for section in pattern.sections)}. "
        f"Medidas: {', '.join(f'{m.key}={m.value_cm:g}cm' for m in pattern.measurements)}. "
        f"Material: {pattern.materials.meters:g} m."
    )


def build_writer_messages(
    pattern: Pattern,
    *,
    language: str | None = None,
    level: str | None = None,
) -> list[Message]:
    canonical = render_pattern_text(pattern, lang=language, level=level)
    return [
        Message.system(WRITER_SYSTEM_PROMPT),
        Message.user_text(
            WRITER_USER_PROMPT.format(
                language=language or pattern.params.idioma,
                level=level or pattern.params.nivel,
                canonical=canonical,
            )
        ),
    ]


@dataclass(frozen=True)
class WriterResult:
    text: str
    fallback_used: bool
    attempts: int
    validation_errors: tuple[str, ...]
    prompt_version: str
    usage: Usage
    cached: bool


def _merge_usage(total: Usage, extra: Usage) -> Usage:
    return Usage(
        prompt_tokens=total.prompt_tokens + extra.prompt_tokens,
        completion_tokens=total.completion_tokens + extra.completion_tokens,
        total_tokens=total.total_tokens + extra.total_tokens,
        cost_usd=total.cost_usd + extra.cost_usd,
    )


async def write_pattern_text(
    pattern: Pattern,
    *,
    language: str | None = None,
    level: str | None = None,
    config: AIConfig | None = None,
    client: AIClient | None = None,
    max_attempts: int = 3,
) -> WriterResult:
    """Reescribe el patron; si la IA no respeta los numeros, usa la plantilla."""
    chosen_config = config or AIConfig.from_env()
    lang = language or pattern.params.idioma
    difficulty = level or pattern.params.nivel
    canonical = render_pattern_text(pattern, lang=lang, level=difficulty)
    allowed = allowed_numbers(pattern, lang)
    own_client = client is None
    if client is None:
        if chosen_config.fake:
            client = FakeAIClient(
                handler=lambda messages, model, response_format: canonical
            )
        else:
            client = OpenAICompatibleClient(chosen_config)

    messages = build_writer_messages(pattern, language=lang, level=difficulty)
    usage = Usage()
    cached = True
    errors: list[str] = []
    attempts = 0
    try:
        for _ in range(max(1, max_attempts)):
            attempts += 1
            try:
                response: AIResponse = await client.complete(
                    messages,
                    model=chosen_config.model_for("writer"),
                    temperature=0.3,
                    max_tokens=2500,
                )
            except AIError as exc:
                errors.append(str(exc))
                break
            usage = _merge_usage(usage, response.usage)
            cached = cached and response.cached
            unknown = unknown_numbers(response.text, allowed)
            if not unknown:
                return WriterResult(
                    text=response.text.strip(),
                    fallback_used=False,
                    attempts=attempts,
                    validation_errors=tuple(errors),
                    prompt_version=WRITER_PROMPT_VERSION,
                    usage=usage,
                    cached=cached,
                )
            rendered = ", ".join(f"{number:g}" for number in unknown)
            errors.append(f"numeros no permitidos: {rendered}")
            messages.append(Message.text("assistant", response.text))
            messages.append(
                Message.user_text(WRITER_REPAIR_PROMPT.format(unknown=rendered))
            )
    finally:
        if own_client:
            await client.aclose()
    return WriterResult(
        text=canonical,
        fallback_used=True,
        attempts=attempts,
        validation_errors=tuple(errors),
        prompt_version=WRITER_PROMPT_VERSION,
        usage=usage,
        cached=cached,
    )


def writer_summary(pattern: Pattern) -> str:
    return _summary(pattern)
