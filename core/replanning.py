from dataclasses import dataclass, asdict
from datetime import datetime
import uuid


@dataclass
class ReplanDecision:
    replan_id: str
    task_id: str
    reason: str
    failed_assumption: str
    alternatives: list[str]
    selected: str
    timestamp: str


class Replanner:
    """Minimal evidence-driven replanning primitive; avoids blind retries."""
    def __init__(self, events):
        self.events = events

    def replan(self, task_id, reason, failed_assumption='', alternatives=None):
        alternatives = list(alternatives or [])
        selected = alternatives[0] if alternatives else 'inspect_and_rebuild_plan'
        decision = ReplanDecision(
            f'replan-{uuid.uuid4().hex[:12]}', task_id, reason,
            failed_assumption, alternatives, selected,
            datetime.now().isoformat(timespec='seconds'))
        self.events.emit('replan_triggered', asdict(decision))
        return decision
