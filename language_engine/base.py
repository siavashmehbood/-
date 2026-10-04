"""Backend-neutral contracts for IRAN's multilingual language engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence


@dataclass(frozen=True)
class GenerationRequest:
    messages: Sequence[Mapping[str, str]]
    language: str = "fa"
    max_tokens: int = 512
    temperature: float = 0.2
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationResult:
    text: str
    backend: str
    model: str
    latency_ms: float = 0.0
    metadata: Mapping[str, object] = field(default_factory=dict)


class LanguageBackend(Protocol):
    """A subordinate generator. It never owns memory, tools, learning or decisions."""
    name: str
    model: str

    def generate(self, request: GenerationRequest) -> GenerationResult: ...
