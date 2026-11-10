"""Extractor de atributos con vision: muestras, votacion y reparacion.

La IA solo interpreta. Ningun campo de este modulo es una medida ni un conteo
de puntos; esos numeros los calcula `engine/`.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ai.client import AIClient, OpenAICompatibleClient
from ai.config import AIConfig
from ai.errors import AIError, ExtractionError
from ai.fake import FakeAIClient
from ai.prompts.extractor_v1 import (
    EXTRACTOR_PROMPT_VERSION,
    EXTRACTOR_REPAIR_PROMPT,
    EXTRACTOR_SYSTEM_PROMPT,
    EXTRACTOR_USER_PROMPT,
    extractor_response_format,
)
from ai.types import AIResponse, ImagePart, Message, TextPart, Usage
from engine.spec import GarmentSpec
from vision.preprocess import PreparedImage

VOTED_FIELDS = (
    "categoria",
    "tecnica",
    "construccion",
    "escote",
    "largo_cuerpo",
    "largo_manga",
    "ajuste",
    "forma",
    "punto_base",
    "texturas",
    "colorwork",
    "acabados",
    "hilo_aparente",
    "observaciones",
)
UNION_FIELDS = ("incertidumbres", "no_visible")


@dataclass(frozen=True)
class ExtractionResult:
    spec: GarmentSpec
    samples: tuple[GarmentSpec, ...]
    confidence: dict[str, float]
    disagreements: dict[str, tuple[str, ...]]
    prompt_version: str
    usage: Usage
    cached: bool


def _canonical(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in value
        ]
    if hasattr(value, "value"):
        value = value.value
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _majority(values: list[Any]) -> tuple[Any, int, tuple[str, ...]]:
    canonical = [_canonical(value) for value in values]
    counts = Counter(canonical)
    best_count = max(counts.values())
    tied = sorted(key for key, count in counts.items() if count == best_count)
    winner = tied[0]
    losers = tuple(sorted(key for key in counts if key != winner))
    for value, key in zip(values, canonical, strict=True):
        if key == winner:
            return value, best_count, losers
    raise AssertionError("no se encontro el valor ganador")


def consolidate(samples: list[GarmentSpec]) -> ExtractionResult:
    if not samples:
        raise ExtractionError("no hay muestras validas para consolidar")
    total = len(samples)
    confidence: dict[str, float] = {}
    disagreements: dict[str, tuple[str, ...]] = {}
    chosen: dict[str, Any] = {}
    for field in VOTED_FIELDS:
        values = [getattr(sample, field) for sample in samples]
        winner, count, losers = _majority(values)
        chosen[field] = winner
        confidence[field] = count / total
        if losers:
            disagreements[field] = losers
    uncertainties = sorted(
        {item for sample in samples for item in sample.incertidumbres}
        | {f"desacuerdo en {field}" for field in disagreements}
    )
    no_visible = sorted({item for sample in samples for item in sample.no_visible})
    spec = GarmentSpec(
        **chosen,
        incertidumbres=uncertainties,
        no_visible=no_visible,
        confianza=confidence,
    )
    usage = Usage()
    return ExtractionResult(
        spec=spec,
        samples=tuple(samples),
        confidence=confidence,
        disagreements=disagreements,
        prompt_version=EXTRACTOR_PROMPT_VERSION,
        usage=usage,
        cached=False,
    )


def build_messages(prepared: PreparedImage) -> list[Message]:
    crop_names = ", ".join(prepared.crops) if prepared.crops else "ninguno"
    parts: list[TextPart | ImagePart] = [
        TextPart(
            EXTRACTOR_USER_PROMPT.format(
                crops=crop_names,
                crop_names=crop_names,
            )
        ),
        ImagePart(prepared.main, prepared.mime_type),
    ]
    for name, data in prepared.crops.items():
        parts.append(TextPart(f"Recorte {name}:"))
        parts.append(ImagePart(data, "image/jpeg"))
    return [
        Message.system(EXTRACTOR_SYSTEM_PROMPT),
        Message(role="user", parts=tuple(parts)),
    ]


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


async def _sample_once(
    client: AIClient,
    config: AIConfig,
    messages: list[Message],
) -> tuple[GarmentSpec, AIResponse]:
    conversation = list(messages)
    use_schema = True
    last_error = "respuesta invalida"
    attempts = 0
    while attempts < 3:
        attempts += 1
        try:
            response = await client.complete(
                conversation,
                model=config.model_for("extractor"),
                response_format=extractor_response_format() if use_schema else None,
                temperature=0.4,
                max_tokens=1600,
            )
        except AIError:
            if use_schema:
                use_schema = False
                attempts -= 1
                continue
            raise
        try:
            return GarmentSpec.model_validate(_parse_json(response.text)), response
        except (ValueError, ValidationError) as exc:
            last_error = str(exc)[:800]
            conversation.append(Message.text("assistant", response.text))
            conversation.append(
                Message.user_text(EXTRACTOR_REPAIR_PROMPT.format(error=last_error))
            )
    raise ExtractionError(
        f"no se pudo validar la salida del extractor tras 3 intentos: {last_error}"
    )


def _fake_payload() -> dict[str, Any]:
    return {
        "observaciones": "Prenda tejida de muestra con cuerpo liso y mangas largas.",
        "categoria": "pullover",
        "tecnica": "needles",
        "construccion": "raglan_top_down",
        "escote": "crew",
        "largo_cuerpo": "hip",
        "largo_manga": "long",
        "ajuste": "regular",
        "forma": "straight",
        "punto_base": "stockinette",
        "texturas": [],
        "colorwork": None,
        "acabados": ["cuffs", "hem_band", "neckband"],
        "hilo_aparente": {"grosor_estimado": "dk", "aspecto": "smooth"},
        "incertidumbres": [],
        "no_visible": ["espalda", "manga completa"],
        "confianza": {},
    }


def _fake_handler() -> Any:
    def handler(
        messages: list[Message], model: str, response_format: dict[str, Any] | None
    ) -> str:
        return json.dumps(_fake_payload(), ensure_ascii=False)

    return handler


async def extract_garment(
    prepared: PreparedImage,
    config: AIConfig,
    *,
    client: AIClient | None = None,
    samples: int | None = None,
) -> ExtractionResult:
    """Ejecuta N muestras, valida y consolida campo por campo."""
    own_client = client is None
    if client is None:
        client = (
            FakeAIClient(handler=_fake_handler())
            if config.fake
            else OpenAICompatibleClient(config)
        )
    count = max(1, samples or config.extractor_samples)
    messages = build_messages(prepared)
    valid: list[GarmentSpec] = []
    errors: list[str] = []
    usage = Usage()
    cached = True
    try:
        for _ in range(count):
            try:
                spec, response = await _sample_once(client, config, messages)
            except ExtractionError as exc:
                errors.append(str(exc))
                continue
            valid.append(spec)
            usage = Usage(
                prompt_tokens=usage.prompt_tokens + response.usage.prompt_tokens,
                completion_tokens=usage.completion_tokens
                + response.usage.completion_tokens,
                total_tokens=usage.total_tokens + response.usage.total_tokens,
                cost_usd=usage.cost_usd + response.usage.cost_usd,
            )
            cached = cached and response.cached
    finally:
        if own_client:
            await client.aclose()
    if not valid:
        raise ExtractionError(
            "ninguna muestra del extractor fue valida: " + "; ".join(errors[:3])
        )
    result = consolidate(valid)
    return ExtractionResult(
        spec=result.spec,
        samples=result.samples,
        confidence=result.confidence,
        disagreements=result.disagreements,
        prompt_version=result.prompt_version,
        usage=usage,
        cached=cached,
    )
