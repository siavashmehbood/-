"""Declarative candidate manifests; model weights are never stored in Git."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CandidateManifest:
    candidate_id: str
    family: str
    model_id: str
    revision: str
    license_id: str
    quantization: str = "reference"
    context_length: int = 0
    local_capable: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self):
        if not all((self.candidate_id, self.family, self.model_id, self.revision, self.license_id)):
            raise ValueError("candidate identity, revision and license are required")
        if not self.local_capable:
            raise ValueError("foundation candidate must support local/offline inference")
        if self.context_length < 0:
            raise ValueError("context_length cannot be negative")
        return self
