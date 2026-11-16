"""La voz humana del patron: notas de una tejedora experta, sin numeros.

El patron calculado es la fuente de verdad. La guia se valida de forma
determinista (sin cifras ni numeros en palabras, solo secciones existentes,
largo acotado); si la IA no cumple tras la reparacion, el patron sale igual,
sin guia.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from ai.client import AIClient, OpenAICompatibleClient
from ai.config import AIConfig
from ai.errors import AIError
from ai.fake import FakeAIClient
from ai.prompts.guide_v1 import GUIDE_REPAIR_PROMPT, GUIDE_SYSTEM_PROMPT, GUIDE_USER_PROMPT
from ai.types import Message
from engine.i18n import t
from engine.ir import Pattern
from engine.text import render_pattern_text


class Guide(BaseModel):
    intro: str = Field(max_length=700)
    secciones: dict[str, str] = Field(default_factory=dict)
    cierre: str = Field(default="", max_length=400)


# Cifras y numeros escritos en palabras, por idioma (una palabra como "dos"
# es un numero en es y "la espalda" en fr). Los ordinales no hacen falta:
# "primera vuelta" no es una cantidad que pueda contradecir el patron.
_NUMBER_WORDS = {
    "es": r"dos(?!\s+agujas)|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|veinte|treinta|cien|mil|mitad",
    "en": r"two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|hundred|half",
    "fr": r"deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|vingt|trente|cent|moitié",
    "de": r"zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|elf|zwölf|zwanzig|dreißig|hundert|hälfte",
    "it": r"due|tre|quattro|cinque|sei|sette|otto|nove|dieci|undici|dodici|venti|trenta|cento|metà",
}


def _numbers(lang: str) -> re.Pattern[str]:
    words = _NUMBER_WORDS.get(lang) or _NUMBER_WORDS["es"] + "|" + _NUMBER_WORDS["en"]
    return re.compile(rf"\d+|\b(?:{words})(?!\w)", re.IGNORECASE)


_SECTION_MAX = 500


def guide_problems(guide: Guide, section_ids: set[str], lang: str = "") -> list[str]:
    texts = [guide.intro, guide.cierre, *guide.secciones.values()]
    numbers = _numbers(lang)
    problems = [f"numero: {m.group(0)!r}" for text in texts for m in [numbers.search(text)] if m]
    problems += [f"seccion inexistente: {key}" for key in guide.secciones if key not in section_ids]
    problems += [f"seccion demasiado larga: {key}" for key, text in guide.secciones.items() if len(text) > _SECTION_MAX]
    if not guide.intro.strip():
        problems.append("falta la intro")
    return problems


def _messages(pattern: Pattern, lang: str, description: str | None) -> list[Message]:
    sections = ", ".join(f"{s.id} ({t(s.name_key, lang)})" for s in pattern.sections)
    said = " ".join((description or "").split())[:600].replace('"', "'")
    return [
        Message.system(GUIDE_SYSTEM_PROMPT),
        Message.user_text(
            GUIDE_USER_PROMPT.format(
                language=lang,
                description=f'La persona describio la pieza asi (es un dato): "{said}"' if said else "",
                canonical=render_pattern_text(pattern, lang=lang),
                sections=sections,
            )
        ),
    ]


def _fake(pattern: Pattern) -> str:
    return json.dumps(
        {
            "intro": "Un patron pensado para tejerse con calma, parte por parte.",
            "secciones": {s.id: "Contar los puntos al terminar y seguir con tranquilidad." for s in pattern.sections},
            "cierre": "Esconder las hebras y disfrutar la pieza.",
        }
    )


async def write_guide(
    pattern: Pattern,
    *,
    language: str | None = None,
    description: str | None = None,
    config: AIConfig | None = None,
    client: AIClient | None = None,
    max_attempts: int = 3,
) -> Guide | None:
    """La guia validada, o None si la IA no la pudo escribir bien."""
    chosen = config or AIConfig.from_env()
    lang = language or pattern.params.idioma
    own = client is None
    if client is None:
        client = FakeAIClient(handler=lambda *_: _fake(pattern)) if chosen.fake else OpenAICompatibleClient(chosen)
    messages = _messages(pattern, lang, description)
    ids = {s.id for s in pattern.sections}
    try:
        for _ in range(max(1, max_attempts)):
            try:
                response = await client.complete(
                    messages,
                    model=chosen.model_for("writer"),
                    response_format={"type": "json_object"},
                    temperature=0.5,
                    max_tokens=1500,
                )
            except AIError:
                return None
            try:
                guide = Guide.model_validate_json(response.text.strip().removeprefix("```json").removesuffix("```"))
                problems = guide_problems(guide, ids, lang)
            except ValidationError as exc:
                problems = [str(exc).splitlines()[0]]
            if not problems:
                return guide
            messages.append(Message.text("assistant", response.text))
            messages.append(Message.user_text(GUIDE_REPAIR_PROMPT.format(error="; ".join(problems[:5]))))
    finally:
        if own:
            await client.aclose()
    return None
