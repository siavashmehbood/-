"""Single stable language-engine facade visible to IRAN."""
from __future__ import annotations
from .base import GenerationRequest, GenerationResult, LanguageBackend


class IranLanguageEngine:
    """Vendor-neutral multilingual generator below CognitiveSystem.

    This object deliberately has no memory/tool/learning authority.  CognitiveSystem
    remains the ONE BRAIN and may replace this backend without architectural surgery.
    """
    def __init__(self, backend: LanguageBackend):
        self.backend = backend

    @property
    def identity(self):
        return {"backend": self.backend.name, "model": self.backend.model}

    def generate(self, request: GenerationRequest) -> GenerationResult:
        result = self.backend.generate(request)
        if not isinstance(result, GenerationResult):
            raise TypeError("language backend must return GenerationResult")
        if not str(result.text).strip():
            raise ValueError("language backend returned an empty response")
        return result
