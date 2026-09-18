"""Canonical cognitive state shared by all local cognition layers."""
from dataclasses import dataclass, field, asdict
from datetime import datetime

@dataclass
class CognitiveState:
    # Language/cognitive-engine fields (kept first for legacy positional construction).
    intent: str = "general"
    goal: str = ""
    entities: list = field(default_factory=list)
    constraints: list = field(default_factory=list)
    needs_tools: bool = False
    confidence: float = 0.0
    questions: list = field(default_factory=list)
    temporal: list = field(default_factory=list)
    hypotheses: list = field(default_factory=list)
    domains: list = field(default_factory=list)
    semantic_features: dict = field(default_factory=dict)
    # Advanced cognitive fields.
    turn_id: int = 0
    text: str = ""
    intent_confidence: float = 0.45
    topic: str = ""
    references: dict = field(default_factory=dict)
    evidence: list = field(default_factory=list)
    contradictions: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    plan: list = field(default_factory=list)
    status: str = "idle"
    # Autonomous-cycle fields.
    cycle_id: int = 0
    active_goal: str | None = None
    observations: list = field(default_factory=list)
    predictions: list = field(default_factory=list)
    decision: dict = field(default_factory=dict)
    last_action: dict = field(default_factory=dict)
    last_outcome: dict = field(default_factory=dict)
    uncertainty: float = 1.0
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def snapshot(self):
        return asdict(self)
