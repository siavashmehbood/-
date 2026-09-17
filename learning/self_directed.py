"""Deterministic, topic-directed learning control for IRAN.

This layer decides *what is worth learning* before trusted knowledge is
accepted. It does not fetch data, use models, or modify source code.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib
import re


@dataclass
class LearningGoal:
    goal_id: str
    topic: str
    gap: str
    objective: str
    priority: str
    status: str = "needs_evidence"
    created_at: str = ""


class SelfDirectedLearning:
    """Build and score learning goals from the active topic and evidence."""

    def __init__(self, max_goals=500):
        self.max_goals = int(max_goals)
        self.goals = []

    @staticmethod
    def _tokens(text):
        return set(re.findall(r"[\wآ-ی]+", str(text).lower()))

    @classmethod
    def relevance(cls, topic, text):
        a, b = cls._tokens(topic), cls._tokens(text)
        if not a or not b:
            return 0.0
        overlap = len(a & b) / max(1, len(a))
        coverage = len(a & b) / max(1, len(a | b))
        return round(min(1.0, overlap * .75 + coverage * .25), 4)

    @classmethod
    def _stable_id(cls, topic, gap, objective):
        raw = f"{topic}|{gap}|{objective}".encode("utf-8")
        return "goal_" + hashlib.sha256(raw).hexdigest()[:16]

    def create_goal(self, topic, gap="دانش مرتبط کامل نیست", objective=None,
                    priority="medium"):
        topic = str(topic).strip()
        objective = objective or f"تکمیل دانش مرتبط درباره {topic}"
        gid = self._stable_id(topic, gap, objective)
        existing = next((g for g in self.goals if g.goal_id == gid), None)
        if existing:
            return asdict(existing)
        goal = LearningGoal(gid, topic, str(gap), str(objective), str(priority),
                            created_at=datetime.now().isoformat(timespec="seconds"))
        self.goals.append(goal)
        self.goals = self.goals[-self.max_goals:]
        return asdict(goal)

    def assess(self, topic, evidence_text, known_text="", source_confidence=0.0):
        """Return a learning decision; irrelevant evidence is never accepted."""
        rel = self.relevance(topic, evidence_text)
        known_rel = self.relevance(topic, known_text) if known_text else 0.0
        novelty = round(max(0.0, rel - known_rel * .65), 4)
        confidence = max(0.0, min(1.0, float(source_confidence)))
        useful = rel >= .22 and (novelty >= .08 or not known_text) and confidence >= .35
        if rel < .22:
            reason = "topic_mismatch"
        elif confidence < .35:
            reason = "weak_evidence"
        elif novelty < .08 and known_text:
            reason = "already_known_or_low_novelty"
        else:
            reason = "relevant_gap_candidate"
        priority = "high" if rel >= .65 and novelty >= .20 else "medium" if rel >= .40 else "low"
        return {"learn": useful, "topic": str(topic), "relevance": rel,
                "novelty": novelty, "source_confidence": round(confidence, 4),
                "priority": priority, "reason": reason}

    def goal_for(self, topic, evidence_text="", known_text="", source_confidence=0.0):
        decision = self.assess(topic, evidence_text, known_text, source_confidence)
        gap = "شکاف دانشی مرتبط با موضوع" if decision["learn"] else decision["reason"]
        objective = f"تکمیل دانش درباره {str(topic).strip()}"
        goal = self.create_goal(topic, gap, objective, decision["priority"])
        goal["decision"] = decision
        return goal

    def snapshot(self):
        return {"goals": [asdict(g) for g in self.goals], "count": len(self.goals)}
