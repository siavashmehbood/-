"""Deterministic contradiction and answer-quality checks for local IRAN runtime."""
from dataclasses import dataclass, field
import re


@dataclass
class VerificationResult:
    accepted: bool
    score: float
    reasons: list = field(default_factory=list)
    contradictions: list = field(default_factory=list)


class SemanticVerifier:
    """Checks answer consistency against the current question and known constraints."""

    STOP = {"و", "یا", "که", "را", "به", "از", "در", "برای", "با", "این", "آن"}

    @classmethod
    def tokens(cls, text):
        words = re.findall(r"[\wآ-ی]+", str(text or "").lower())
        return {w for w in words if len(w) > 1 and w not in cls.STOP}

    @classmethod
    def overlap(cls, a, b):
        x, y = cls.tokens(a), cls.tokens(b)
        return len(x & y) / max(1, len(x | y))

    def verify(self, question, answer, constraints=None, rejected_answers=None):
        constraints = constraints or []
        rejected_answers = rejected_answers or []
        reasons = []
        contradictions = []
        q = str(question or "").strip()
        a = str(answer or "").strip()
        if not a:
            return VerificationResult(False, 0.0, ["empty_answer"], [])
        score = .72
        if self.overlap(q, a) >= .08:
            score += .08
        else:
            reasons.append("low_question_alignment")
        low_a = a.lower()
        for constraint in constraints:
            c = str(constraint).lower()
            if c == "آفلاین" and any(x in low_a for x in ("api", "شبکه", "سرویس آنلاین", "cloud")):
                contradictions.append("offline_constraint")
            if c == "بدون api" and ("api" in low_a or "مدل آماده" in low_a):
                contradictions.append("no_api_constraint")
        if contradictions:
            score -= .45
            reasons.append("constraint_contradiction")
        for rejected in rejected_answers:
            if self.overlap(a, rejected) >= .72:
                contradictions.append("repeats_rejected_answer")
                score -= .35
                break
        score = max(0.0, min(1.0, score))
        return VerificationResult(score >= .70 and not contradictions, score, reasons, contradictions)


# The verifier is intentionally a second, narrow gate: the existing planner
# verifier remains authoritative for normal answer generation; this layer only
# blocks explicit constraint contradictions or repetition of rejected answers.
