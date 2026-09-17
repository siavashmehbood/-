from dataclasses import dataclass


@dataclass
class ExecutionDecision:
    success: bool
    reason: str
    should_replan: bool
    attempt: int
    max_replans: int


class AdaptiveExecutionPolicy:
    """Deterministic execution gate: evidence + expected effect + bounded replanning."""

    def __init__(self, max_replans=1):
        self.max_replans = max(0, int(max_replans))

    @staticmethod
    def verify(expected, actual, evidence):
        expected_text = str(expected or '').strip().lower()
        actual_text = str(actual if actual is not None else '').strip().lower()
        if not evidence:
            return False, 'insufficient evidence'
        if expected_text and expected_text not in actual_text:
            return False, 'observed result does not satisfy expected effect'
        return True, 'evidence-backed expected effect'

    def decide(self, expected, actual, evidence, attempt):
        success, reason = self.verify(expected, actual, evidence)
        should_replan = not success and int(attempt) <= self.max_replans
        return ExecutionDecision(success, reason, should_replan,
                                 int(attempt), self.max_replans)
