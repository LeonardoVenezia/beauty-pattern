"""Prompt versionado del critico de patrones."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

CRITIC_PROMPT_VERSION = "critic-v1"

CRITIC_SYSTEM_PROMPT = """Sos una revisora experimentada de tejido.
Tu tarea es senalar posibles incoherencias entre una foto, los atributos
confirmados y un patron ya calculado. Sos solo informativa: nunca modifiques
el patron ni des numeros nuevos.

Respondé en JSON con esta forma exacta:
{"observaciones": ["..."], "riesgos": ["..."]}
- observaciones: cosas que la foto sugiere y el patron no refleja.
- riesgos: dudas o cuidados para quien teje.
- No inventes medidas ni conteos. Si no hay nada para decir, usa listas vacias.
"""

CRITIC_USER_PROMPT = """Idioma de salida: {language}.

Atributos confirmados de la foto:
{spec}

Resumen del patron calculado:
{summary}

Mira la foto y el resumen. Senala solo incoherencias probables y cuidados.
No cambies ningun numero ni propongas un patron alternativo.
"""


class Critique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observaciones: list[str] = Field(default_factory=list)
    riesgos: list[str] = Field(default_factory=list)


def critic_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "critique",
            "strict": True,
            "schema": Critique.model_json_schema(),
        },
    }

CRITIC_REPAIR_PROMPT = """Tu respuesta anterior no es un JSON valido para el
esquema pedido: {error}

Respondé de nuevo solo con JSON: {"observaciones": ["..."], "riesgos": ["..."]}.
"""
