"""Tipos de mensajes y respuestas de la capa de IA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class ImagePart:
    data: bytes
    mime_type: str = "image/jpeg"


ContentPart = TextPart | ImagePart
Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    parts: tuple[ContentPart, ...]

    @classmethod
    def text(cls, role: Role, text: str) -> Message:
        return cls(role=role, parts=(TextPart(text),))

    @classmethod
    def user_text(cls, text: str) -> Message:
        return cls.text("user", text)

    @classmethod
    def system(cls, text: str) -> Message:
        return cls.text("system", text)


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class AIResponse:
    text: str
    model: str
    usage: Usage = field(default_factory=Usage)
    raw: dict[str, Any] | None = None
    cached: bool = False
    latency_ms: float = 0.0
    tool_calls: tuple[dict[str, Any], ...] = ()
