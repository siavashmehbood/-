"""Deployment measurements kept separate from semantic quality scores."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class DeploymentMetrics:
    first_token_ms: float = 0.0
    total_latency_ms: float = 0.0
    tokens_per_second: float = 0.0
    peak_ram_mb: float = 0.0
    peak_vram_mb: float = 0.0
    context_tokens: int = 0
    cpu_fallback: bool = False

    def to_dict(self):
        return dict(self.__dict__)
