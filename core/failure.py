from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class FailureDiagnosis:
    category: str
    reason: str
    failed_assumption: str = ''
    recoverable: bool = True
    timestamp: str = ''


class FailureIntelligence:
    CATEGORIES = {
        'execution': 'execution_failure', 'planning': 'planning_failure',
        'reasoning': 'reasoning_failure', 'memory': 'memory_failure',
        'tool': 'tool_failure', 'environment': 'environment_failure',
        'assumption': 'assumption_failure', 'verification': 'verification_failure',
        'resource': 'resource_failure',
    }

    def diagnose(self, reason, category='verification', failed_assumption=''):
        diagnosis = FailureDiagnosis(
            self.CATEGORIES.get(category, 'verification_failure'), reason,
            failed_assumption, True, datetime.now().isoformat(timespec='seconds'))
        return diagnosis

    def as_event(self, diagnosis):
        return asdict(diagnosis)
