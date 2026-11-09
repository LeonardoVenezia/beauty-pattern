"""Cliente falso para tests y para FAKE_AI=1: sin red ni costo."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from ai.types import AIResponse, Message, TextPart, Usage

FakeHandler = Callable[[Sequence[Message], str, dict[str, Any] | None], str]


@dataclass
class FakeCall:
    messages: tuple[Message, ...]
    model: str
    response_format: dict[str, Any] | None
    temperature: float
    max_tokens: int | None


@dataclass
class FakeAIClient:
    responses: list[str] = field(default_factory=list)
    handler: FakeHandler | None = None
    calls: list[FakeCall] = field(default_factory=list)

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AIResponse:
        chosen = model or "fake"
        self.calls.append(
            FakeCall(
                messages=tuple(messages),
                model=chosen,
                response_format=response_format,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
        if self.handler is not None:
            text = self.handler(messages, chosen, response_format)
        elif self.responses:
            text = self.responses.pop(0)
        elif response_format is not None:
            text = json.dumps({"ok": True})
        else:
            text = "ok"
        return AIResponse(
            text=text,
            model=chosen,
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0, cost_usd=0.0),
        )

    async def aclose(self) -> None:
        return None


def messages_text(messages: Sequence[Message]) -> str:
    chunks: list[str] = []
    for message in messages:
        for part in message.parts:
            if isinstance(part, TextPart):
                chunks.append(part.text)
    return "\n".join(chunks)
