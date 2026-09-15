from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedInput:
    raw_text: str
    normalized_text: str
    intent: str = 'general'
    question_type: str = 'none'
    entities: list[Any] = field(default_factory=list)
    references: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    negated: bool = False
    confidence: float = 0.0


@dataclass
class FinalAnswer:
    text: str
    mode: str = 'UNKNOWN'
    confidence: float = 0.0
    evidence: list[Any] = field(default_factory=list)
    next_step: str = ''
    unknown: bool = False


@dataclass
class CognitiveTrace:
    turn_id: str
    mode: str
    confidence: float
    evidence_count: int = 0
    plan_version: int | None = None
    learned: bool = False
