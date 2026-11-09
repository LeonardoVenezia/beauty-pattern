"""Configuracion de la IA, 100 % por variables de entorno.

No hay URLs ni ids de modelo escritos en el codigo. `.env.example` documenta
los valores del proveedor Refuseless verificados en su documentacion.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ai.errors import AIConfigError

Role = Literal["extractor", "writer", "critic"]


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on", "si"}


def _as_float(value: str | None, default: float) -> float:
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise AIConfigError(f"valor numerico invalido: {value!r}") from exc


def _as_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise AIConfigError(f"valor entero invalido: {value!r}") from exc


@dataclass(frozen=True)
class AIConfig:
    provider: str
    base_url: str | None
    api_key: str | None
    model: str | None
    model_extractor: str | None = None
    model_writer: str | None = None
    model_critic: str | None = None
    fake: bool = False
    timeout_s: float = 60.0
    max_retries: int = 2
    extractor_samples: int = 3
    cache_dir: Path = Path(".ai-cache")
    price_input_per_mtok: float = 0.0
    price_output_per_mtok: float = 0.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> AIConfig:
        values = os.environ if env is None else env
        fake = _as_bool(values.get("FAKE_AI"))
        model = (values.get("AI_MODEL") or "").strip() or None
        if not fake and model is None:
            raise AIConfigError("AI_MODEL no esta definido (y FAKE_AI no esta activo)")
        if not fake and not (values.get("AI_BASE_URL") or "").strip():
            raise AIConfigError("AI_BASE_URL no esta definido")
        if not fake and not (values.get("AI_API_KEY") or "").strip():
            raise AIConfigError("AI_API_KEY no esta definido")
        return cls(
            provider=(values.get("AI_PROVIDER") or "refuseless").strip(),
            base_url=(values.get("AI_BASE_URL") or "").strip() or None,
            api_key=(values.get("AI_API_KEY") or "").strip() or None,
            model=model or ("fake" if fake else None),
            model_extractor=(values.get("AI_MODEL_EXTRACTOR") or "").strip() or None,
            model_writer=(values.get("AI_MODEL_WRITER") or "").strip() or None,
            model_critic=(values.get("AI_MODEL_CRITIC") or "").strip() or None,
            fake=fake,
            timeout_s=_as_float(values.get("AI_TIMEOUT_S"), 60.0),
            max_retries=_as_int(values.get("AI_MAX_RETRIES"), 2),
            extractor_samples=max(1, _as_int(values.get("AI_EXTRACTOR_SAMPLES"), 3)),
            cache_dir=Path(values.get("AI_CACHE_DIR") or ".ai-cache"),
            price_input_per_mtok=_as_float(values.get("AI_PRICE_INPUT_PER_MTOK"), 0.0),
            price_output_per_mtok=_as_float(values.get("AI_PRICE_OUTPUT_PER_MTOK"), 0.0),
        )

    def model_for(self, role: Role) -> str:
        if self.fake:
            return "fake"
        specific = {
            "extractor": self.model_extractor,
            "writer": self.model_writer,
            "critic": self.model_critic,
        }[role]
        chosen = specific or self.model
        if chosen is None:
            raise AIConfigError(f"no hay modelo configurado para el rol {role}")
        return chosen

    def require_endpoint(self) -> tuple[str, str, str]:
        if self.fake:
            return ("fake", "fake", "fake")
        if not self.base_url or not self.api_key or not self.model:
            raise AIConfigError(
                "faltan AI_BASE_URL, AI_API_KEY o AI_MODEL para usar la IA real"
            )
        return (self.base_url, self.api_key, self.model)
