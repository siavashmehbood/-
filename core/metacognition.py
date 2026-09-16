"""Deterministic metacognitive monitor for confidence and answer quality."""
from dataclasses import dataclass, field

@dataclass
class MetaAssessment:
    confidence: float
    evidence_strength: float
    ambiguity: float
    issues: list[str] = field(default_factory=list)
    recommendation: str = "answer"

class MetacognitiveMonitor:
    def assess(self, confidence, evidence_count=0, contradictions=0, unresolved=0):
        c = max(0.0, min(1.0, float(confidence)))
        evidence = max(0.0, min(1.0, evidence_count / 5.0))
        ambiguity = max(0.0, min(1.0, 0.25 * unresolved + 0.35 * contradictions + (0.35 if c < .45 else 0.0)))
        issues = []
        if evidence_count == 0: issues.append("no_supporting_evidence")
        if contradictions: issues.append("contradictory_evidence")
        if unresolved: issues.append("unresolved_context")
        if c < .45: issues.append("low_confidence")
        recommendation = "clarify" if ambiguity >= .55 else ("verify" if c < .70 or evidence < .20 else "answer")
        return MetaAssessment(round(c, 3), round(evidence, 3), round(ambiguity, 3), issues, recommendation)

    def reflect(self, assessment, answer):
        text = str(answer or "").strip()
        if not text:
            return {"accept": False, "reason": "empty_answer"}
        if assessment.recommendation == "clarify" and len(text) > 500:
            return {"accept": False, "reason": "too_much_answer_for_ambiguous_state"}
        return {"accept": True, "reason": assessment.recommendation}
