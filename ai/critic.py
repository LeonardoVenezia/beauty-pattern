"""Critico informativo: compara foto, atributos y patron calculado.

Nunca modifica el patron ni produce numeros nuevos. Sus observaciones se
muestran como advertencias para la persona.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ai.client import AIClient, OpenAICompatibleClient
from ai.config import AIConfig
from ai.errors import AIError
from ai.fake import FakeAIClient
from ai.prompts.critic_v1 import (
    CRITIC_PROMPT_VERSION,
    CRITIC_REPAIR_PROMPT,
    CRITIC_SYSTEM_PROMPT,
    CRITIC_USER_PROMPT,
    Critique,
    critic_response_format,
)
from ai.types import AIResponse, ImagePart, Message, Usage
from engine.ir import Pattern
from engine.spec import GarmentSpec
from vision.preprocess import PreparedImage


@dataclass(frozen=True)
class CriticResult:
    observations: tuple[str, ...]
    risks: tuple[str, ...]
    fallback_used: bool
    prompt_version: str
    usage: Usage
    cached: bool


def _parse_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("la respuesta no contiene un objeto JSON")
    payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("la respuesta JSON no es un objeto")
    return payload


def _summary(pattern: Pattern) -> str:
    sections = ", ".join(
        f"{section.id} ({section.start_stitches}->{section.end_stitches})"
        for section in pattern.sections
    )
    measurements = ", ".join(
        f"{item.key}={item.value_cm:g}cm" for item in pattern.measurements
    )
    warnings = ", ".join(warning.code for warning in pattern.warnings) or "ninguna"
    return (
        f"Secciones: {sections}. Medidas: {measurements}. "
        f"Material: {pattern.materials.meters:g} m. Advertencias: {warnings}."
    )


def build_critic_messages(
    prepared: PreparedImage,
    spec: GarmentSpec,
    pattern: Pattern,
    *,
    language: str = "es",
) -> list[Message]:
    return [
        Message.system(CRITIC_SYSTEM_PROMPT),
        Message(
            role="user",
            parts=(
                Message.user_text(
                    CRITIC_USER_PROMPT.format(
                        language=language,
                        spec=spec.model_dump_json(indent=2),
                        summary=_summary(pattern),
                    )
                ).parts[0],
                ImagePart(prepared.main, prepared.mime_type),
            ),
        ),
    ]


def _merge_usage(total: Usage, extra: Usage) -> Usage:
    return Usage(
        prompt_tokens=total.prompt_tokens + extra.prompt_tokens,
        completion_tokens=total.completion_tokens + extra.completion_tokens,
        total_tokens=total.total_tokens + extra.total_tokens,
        cost_usd=total.cost_usd + extra.cost_usd,
    )


def _fake_handler() -> Any:
    def handler(
        messages: list[Message], model: str, response_format: dict[str, Any] | None
    ) -> str:
        return json.dumps(
            {
                "observaciones": [
                    "La foto es una referencia; revisa el largo de manga antes de tejer."
                ],
                "riesgos": ["Teje una muestra para confirmar la densidad."],
            },
            ensure_ascii=False,
        )

    return handler


async def critique_pattern(
    prepared: PreparedImage,
    spec: GarmentSpec,
    pattern: Pattern,
    *,
    language: str = "es",
    config: AIConfig | None = None,
    client: AIClient | None = None,
    max_attempts: int = 3,
) -> CriticResult:
    chosen_config = config or AIConfig.from_env()
    own_client = client is None
    if client is None:
        client = (
            FakeAIClient(handler=_fake_handler())
            if chosen_config.fake
            else OpenAICompatibleClient(chosen_config)
        )
    messages = build_critic_messages(prepared, spec, pattern, language=language)
    usage = Usage()
    cached = True
    attempts = 0
    try:
        for _ in range(max(1, max_attempts)):
            attempts += 1
            try:
                response: AIResponse = await client.complete(
                    messages,
                    model=chosen_config.model_for("critic"),
                    response_format=critic_response_format(),
                    temperature=0.2,
                    max_tokens=1200,
                )
            except AIError:
                break
            usage = _merge_usage(usage, response.usage)
            cached = cached and response.cached
            try:
                critique = Critique.model_validate(_parse_json(response.text))
            except (ValueError, ValidationError) as exc:
                messages.append(Message.text("assistant", response.text))
                messages.append(
                    Message.user_text(
                        CRITIC_REPAIR_PROMPT.replace("{error}", str(exc)[:500])
                    )
                )
                continue
            return CriticResult(
                observations=tuple(critique.observaciones),
                risks=tuple(critique.riesgos),
                fallback_used=False,
                prompt_version=CRITIC_PROMPT_VERSION,
                usage=usage,
                cached=cached,
            )
    finally:
        if own_client:
            await client.aclose()
    return CriticResult(
        observations=(),
        risks=(),
        fallback_used=True,
        prompt_version=CRITIC_PROMPT_VERSION,
        usage=usage,
        cached=cached,
    )
