"""Backend-neutral benchmark runner; no model/network dependency is imported."""
from __future__ import annotations
import time
from language_engine import GenerationRequest
from .scorer import DeterministicScorer


class BenchmarkRunner:
    def __init__(self, engine, scorer=None):
        self.engine = engine
        self.scorer = scorer or DeterministicScorer()

    def run(self, cases):
        rows = []
        for case in cases:
            started = time.monotonic()
            result = self.engine.generate(GenerationRequest(
                messages=case.messages, language=case.language,
                metadata={"case_id": case.case_id, "category": case.category}))
            scored = self.scorer.score(case, result.text)
            rows.append({
                "case_id": case.case_id, "language": case.language,
                "tier": case.tier, "category": case.category,
                "difficulty": case.difficulty, "model": result.model,
                "backend": result.backend, "score": scored["score"],
                "latency_ms": round((time.monotonic() - started) * 1000, 3),
                "scoring": scored,
            })
        return rows
