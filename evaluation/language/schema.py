"""Validated benchmark schema shared by all foundation candidates."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    language: str
    tier: str
    category: str
    difficulty: str
    messages: Sequence[Mapping[str, str]]
    rubric: Sequence[str] = field(default_factory=tuple)
    expected_facts: Sequence[str] = field(default_factory=tuple)
    forbidden_claims: Sequence[str] = field(default_factory=tuple)
    scoring_method: str = "rubric"
    max_score: float = 100.0

    def validate(self):
        if not self.case_id or not self.language or not self.category:
            raise ValueError("case_id, language and category are required")
        if self.tier not in {"persian", "tier1", "stress"}:
            raise ValueError("invalid benchmark tier")
        if self.difficulty not in {"easy", "medium", "hard", "adversarial"}:
            raise ValueError("invalid difficulty")
        if not self.messages:
            raise ValueError("benchmark case requires at least one message")
        if self.max_score <= 0:
            raise ValueError("max_score must be positive")
        return self
