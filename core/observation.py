from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any
import uuid


@dataclass
class Observation:
    observation_id: str
    action_id: str
    expected: str
    actual: Any
    evidence: list[Any]
    timestamp: str


class ObservationEngine:
    """Captures post-action evidence separately from action return values."""
    def __init__(self, events):
        self.events = events

    def observe(self, action, actual=None, evidence=None):
        obs = Observation(
            observation_id=f'obs-{uuid.uuid4().hex[:12]}',
            action_id=action.action_id,
            expected=action.expected_effect,
            actual=action.result if actual is None else actual,
            evidence=[] if evidence is None else list(evidence),
            timestamp=datetime.now().isoformat(timespec='seconds'))
        self.events.emit('observation_created', asdict(obs))
        return obs
