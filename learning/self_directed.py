"""Deterministic self-directed learning controller for IRAN.

No network, model, embedding, or external knowledge source is used here.
The controller turns a topic into a bounded learning plan and decides whether
new evidence is relevant, novel, conflicting, and worth learning.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from collections import Counter
import hashlib
import json
import re


_STOP = set("the and or for with from this that are was were is of to in a an on as by".split())
_STOP |= set("و یا از برای با که این آن است را در به یک های هایِ درباره روی از".split())


@dataclass
class LearningGoal:
    goal_id: str
    topic: str
    gap: str
    objective: str
    priority: str
    status: str = "needs_evidence"
    domain: str = "general"
    attempts: int = 0
    evidence_count: int = 0
    success_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class SelfDirectedLearning:
    """Goal-directed learning, gap detection, prioritization and consolidation."""

    def __init__(self, path=None, max_goals=500):
        self.max_goals = int(max_goals)
        self.path = Path(path) if path else None
        self.goals = []
        self.history = []
        self._load()

    @staticmethod
    def _tokens(text):
        words = re.findall(r"[\wآ-ی]+", str(text).lower())
        return {w for w in words if len(w) > 1 and w not in _STOP}

    @classmethod
    def relevance(cls, topic, text):
        a, b = cls._tokens(topic), cls._tokens(text)
        if not a or not b:
            return 0.0
        overlap = len(a & b) / len(a)
        coverage = len(a & b) / max(1, len(a | b))
        return round(min(1.0, overlap * .75 + coverage * .25), 4)

    @classmethod
    def novelty(cls, topic, evidence, known):
        rel = cls.relevance(topic, evidence)
        if not known:
            return rel
        known_tokens = cls._tokens(known)
        evidence_tokens = cls._tokens(evidence)
        if not evidence_tokens:
            return 0.0
        new = len(evidence_tokens - known_tokens) / len(evidence_tokens)
        return round(rel * new, 4)

    @classmethod
    def contradiction(cls, evidence, known):
        """Conservative conflict signal: shared subject terms + explicit negation."""
        if not evidence or not known:
            return 0.0
        e, k = str(evidence).lower(), str(known).lower()
        neg = (" نیست", " نمی ", " نادرست", " false", "not ", "never", "no ")
        e_neg = any(x in e for x in neg)
        k_neg = any(x in k for x in neg)
        shared = cls.relevance(e, k)
        if shared < .20 or e_neg == k_neg:
            return 0.0
        return round(min(1.0, shared), 4)

    @classmethod
    def detect_domain(cls, topic, evidence=""):
        text = f"{topic} {evidence}".lower()
        groups = {
            "programming": ("python", "کد", "برنامه", "حلقه", "تابع", "متغیر", "programming"),
            "mathematics": ("ریاضی", "معادله", "جبر", "هندسه", "عدد", "math", "equation"),
            "language": ("زبان", "گرامر", "واژه", "دستور", "language", "grammar"),
            "science": ("فیزیک", "شیمی", "زیست", "physics", "chemistry", "science"),
        }
        scores = {d: sum(1 for w in words if w in text) for d, words in groups.items()}
        return max(scores, key=scores.get) if scores and max(scores.values()) else "general"

    @staticmethod
    def _stable_id(topic, gap, objective):
        raw = f"{topic}|{gap}|{objective}".encode("utf-8")
        return "goal_" + hashlib.sha256(raw).hexdigest()[:16]

    def _save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"goals": [asdict(g) for g in self.goals], "history": self.history[-2000:]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _load(self):
        if not self.path or not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            rows = payload.get("goals", []) if isinstance(payload, dict) else []
            self.goals = [LearningGoal(**r) for r in rows[-self.max_goals:]]
            self.history = payload.get("history", [])[-2000:] if isinstance(payload, dict) else []
        except Exception:
            self.goals, self.history = [], []

    def create_goal(self, topic, gap="دانش مرتبط کامل نیست", objective=None,
                    priority="medium", domain=None):
        topic = str(topic).strip()
        domain = domain or self.detect_domain(topic)
        objective = objective or f"تکمیل دانش درباره {topic}"
        gid = self._stable_id(topic, gap, objective)
        existing = next((g for g in self.goals if g.goal_id == gid), None)
        now = datetime.now().isoformat(timespec="seconds")
        if existing:
            existing.updated_at = now
            return asdict(existing)
        goal = LearningGoal(gid, topic, str(gap), str(objective), str(priority),
                            domain=domain, created_at=now, updated_at=now)
        self.goals.append(goal)
        self.goals = self.goals[-self.max_goals:]
        self._save()
        return asdict(goal)

    def assess(self, topic, evidence_text, known_text="", source_confidence=0.0):
        rel = self.relevance(topic, evidence_text)
        nov = self.novelty(topic, evidence_text, known_text)
        conflict = self.contradiction(evidence_text, known_text)
        confidence = max(0.0, min(1.0, float(source_confidence)))
        repeated = bool(known_text) and nov < .08
        useful = rel >= .22 and confidence >= .35 and (nov >= .08 or conflict >= .35 or not known_text)
        if rel < .22: reason = "topic_mismatch"
        elif confidence < .35: reason = "weak_evidence"
        elif repeated and conflict < .35: reason = "already_known_or_low_novelty"
        elif conflict >= .35: reason = "relevant_conflict_requires_resolution"
        else: reason = "relevant_gap_candidate"
        priority_score = rel * .45 + nov * .30 + conflict * .20 + confidence * .05
        priority = "high" if priority_score >= .62 or conflict >= .60 else "medium" if priority_score >= .36 else "low"
        return {"learn": useful, "topic": str(topic), "domain": self.detect_domain(topic, evidence_text),
                "relevance": rel, "novelty": nov, "contradiction": conflict,
                "source_confidence": round(confidence, 4), "priority": priority,
                "reason": reason, "needs_resolution": conflict >= .35}

    def goal_for(self, topic, evidence_text="", known_text="", source_confidence=0.0):
        decision = self.assess(topic, evidence_text, known_text, source_confidence)
        gap = ("حل اختلاف شواهد درباره موضوع" if decision["needs_resolution"] else
               "شکاف دانشی مرتبط با موضوع" if decision["learn"] else decision["reason"])
        goal = self.create_goal(topic, gap, f"تکمیل و راستی‌آزمایی دانش درباره {str(topic).strip()}",
                                decision["priority"], decision["domain"])
        goal["decision"] = decision
        return goal

    def next_action(self, goal_or_topic):
        topic = goal_or_topic.get("topic", "") if isinstance(goal_or_topic, dict) else str(goal_or_topic)
        candidates = [g for g in self.goals if g.topic == topic]
        if not candidates:
            return {"action": "define_goal", "topic": topic}
        g = candidates[-1]
        if g.status == "needs_evidence": return {"action": "collect_relevant_evidence", "goal_id": g.goal_id}
        if g.status == "conflict": return {"action": "resolve_conflict", "goal_id": g.goal_id}
        if g.status == "testing": return {"action": "run_knowledge_test", "goal_id": g.goal_id}
        return {"action": "review_or_expand", "goal_id": g.goal_id}

    def update_outcome(self, goal_id, status, evidence_count=None, success=False):
        goal = next((g for g in self.goals if g.goal_id == goal_id), None)
        if not goal: return None
        goal.status = str(status)
        goal.attempts += 1
        if evidence_count is not None: goal.evidence_count += int(evidence_count)
        if success: goal.success_count += 1
        goal.updated_at = datetime.now().isoformat(timespec="seconds")
        self.history.append({"goal_id": goal_id, "status": status, "success": bool(success), "at": goal.updated_at})
        self._save()
        return asdict(goal)

    def prioritize(self, limit=10):
        def score(g):
            base = {"high": .9, "medium": .55, "low": .25}.get(g.priority, .25)
            urgency = 1.0 if g.status in {"needs_evidence", "conflict"} else .55
            return base * .65 + urgency * .25 + min(1.0, g.attempts / 10) * .10
        rows = sorted(self.goals, key=score, reverse=True)
        return [{"goal": asdict(g), "priority_score": round(score(g), 4),
                 "next_action": self.next_action(asdict(g))} for g in rows[:int(limit)]]

    def snapshot(self):
        return {"goals": [asdict(g) for g in self.goals], "count": len(self.goals),
                "priority_queue": self.prioritize(10), "history_count": len(self.history)}
