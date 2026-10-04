"""Deterministic offline backend for CI; never downloads model weights."""
from __future__ import annotations
from language_engine.base import GenerationRequest, GenerationResult


class FixtureBackend:
    name = "fixture"
    model = "iran-language-fixture"

    def __init__(self, responses=None):
        self.responses = dict(responses or {})

    def generate(self, request: GenerationRequest) -> GenerationResult:
        prompt = request.messages[-1].get("content", "") if request.messages else ""
        text = self.responses.get(prompt, prompt or "OK")
        return GenerationResult(text=text, backend=self.name, model=self.model,
                                metadata={"offline": True, "language": request.language})
