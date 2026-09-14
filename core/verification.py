from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class VerificationResult:
    action_id: str
    success: bool
    reason: str
    evidence: list
    checked_at: str


class VerificationEngine:
    """Determines success from observed evidence, not from execution alone."""
    def __init__(self, events):
        self.events = events

    def verify(self, observation, predicate=None):
        if predicate is None:
            success = bool(observation.evidence) and observation.actual is not None
            reason = 'evidence-backed observation' if success else 'insufficient evidence'
        else:
            success = bool(predicate(observation))
            reason = 'predicate accepted' if success else 'predicate rejected'
        result = VerificationResult(observation.action_id, success, reason,
                                    list(observation.evidence),
                                    datetime.now().isoformat(timespec='seconds'))
        self.events.emit('verification_completed', asdict(result))
        return result
