"""Independent outcome-backed learning loop for IRAN.

The loop closes the gap between storing an experience and actually changing
future behavior.  A learning update is accepted only when an outcome is
independently verified; a response score alone is never treated as world
success.

Flow:
    episode -> temporal/context retrieval -> evidence -> lesson ->
    strategy update -> future decision -> independently verified outcome

This module is fully local and deterministic.  It does not use an LLM,
embedding service, or external AI service.
"""
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import json
import math
import re


@dataclass
class Outcome:
    goal: str
    action: str
    result: str
    expected: str
    verified: bool
    verification_source: str
    score: float
    strategy: str = "default"
    domain: str = "general"
    timestamp: str = ""


class OutcomeBackedLearning:
    """Small durable bridge between verified outcomes and LearningEngine.

    Important invariant: ``verified=True`` must come from an independent
    verification step supplied by the caller.  The generated answer or its
    self-score is never sufficient evidence of task success.
    """

    def __init__(self, path, learning_engine=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.learning = learning_engine
        self.records = []
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.records = data[-5000:] if isinstance(data, list) else []
        except Exception:
            self.records = []

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.records[-5000:], ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _tokens(text):
        return set(re.findall(r"[\wآ-ی]+", str(text).lower()))

    @classmethod
    def similarity(cls, a, b):
        x, y = cls._tokens(a), cls._tokens(b)
        return len(x & y) / max(1, len(x | y))

    def retrieve_context(self, goal, domain=None, limit=8):
        """Retrieve prior verified outcomes using goal similarity and recency."""
        now = datetime.now()
        candidates = []
        for row in self.records:
            if domain and row.get("domain") != domain:
                continue
            if not row.get("verified"):
                continue
            sim = self.similarity(goal, row.get("goal", ""))
            if sim <= 0.02:
                continue
            try:
                age_days = max(0.0, (now - datetime.fromisoformat(row["timestamp"])).total_seconds() / 86400)
            except Exception:
                age_days = 3650.0
            recency = math.exp(-age_days / 30.0)
            rank = sim * 0.65 + float(row.get("score", 0.0)) * 0.20 + recency * 0.15
            candidates.append((rank, row))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in candidates[: int(limit)]]

    def lesson(self, goal, domain=None):
        rows = self.retrieve_context(goal, domain, 12)
        if not rows:
            return {
                "lesson": "collect evidence before committing",
                "confidence": 0.35,
                "samples": 0,
                "strategy": "evidence-first",
            }
        good = [r for r in rows if float(r.get("score", 0)) >= 0.75]
        bad = [r for r in rows if float(r.get("score", 0)) < 0.55]
        if len(good) > len(bad):
            strategy = max(good, key=lambda r: float(r.get("score", 0))).get("strategy", "default")
            return {
                "lesson": f"reuse strategy '{strategy}', then independently verify the outcome",
                "confidence": round(min(0.95, 0.45 + len(good) * 0.06), 3),
                "samples": len(rows),
                "strategy": strategy,
            }
        if len(bad) > len(good):
            return {
                "lesson": "change strategy and gather stronger evidence before acting",
                "confidence": round(min(0.90, 0.45 + len(bad) * 0.07), 3),
                "samples": len(rows),
                "strategy": "evidence-first",
            }
        return {
            "lesson": "outcomes are mixed; compare evidence before choosing a strategy",
            "confidence": 0.50,
            "samples": len(rows),
            "strategy": "compare-evidence",
        }

    def record_outcome(self, goal, action, result, expected, verification, strategy="default", domain="general"):
        """Record an outcome and update LearningEngine only after verification.

        ``verification`` is a dict supplied by an independent verifier and must
        contain ``verified``, ``source`` and optionally ``score``.  A missing or
        false verification never enters procedural learning.
        """
        verification = verification if isinstance(verification, dict) else {}
        verified = bool(verification.get("verified", False))
        source = str(verification.get("source", "unknown"))
        if not verified:
            score = 0.0
        else:
            try:
                score = max(0.0, min(1.0, float(verification.get("score", 1.0))))
            except (TypeError, ValueError):
                score = 1.0

        outcome = Outcome(
            goal=str(goal), action=str(action), result=str(result)[:4000], expected=str(expected),
            verified=verified, verification_source=source, score=score,
            strategy=str(strategy), domain=str(domain),
            timestamp=datetime.now().isoformat(timespec="seconds"),
        )
        self.records.append(asdict(outcome))
        self._save()

        learned = False
        if verified and self.learning is not None:
            self.learning.record(
                outcome.goal, outcome.action, outcome.result, outcome.score,
                intent="verified_outcome", strategy=outcome.strategy, domain=outcome.domain,
            )
            learned = True

        return {
            "recorded": True,
            "verified": verified,
            "learned": learned,
            "score": score,
            "verification_source": source,
            "lesson": self.lesson(outcome.goal, outcome.domain),
        }

    def recommend(self, goal, domain="general"):
        """Return a strategy recommendation without claiming success."""
        lesson = self.lesson(goal, domain)
        return {
            "goal": str(goal),
            "recommended_strategy": lesson["strategy"],
            "confidence": lesson["confidence"],
            "evidence_samples": lesson["samples"],
            "lesson": lesson["lesson"],
        }

    def stats(self):
        verified = [r for r in self.records if r.get("verified")]
        return {
            "records": len(self.records),
            "verified_records": len(verified),
            "unverified_records": len(self.records) - len(verified),
            "verified_success_rate": round(sum(float(r.get("score", 0)) >= 0.75 for r in verified) / len(verified), 3) if verified else 0.0,
        }
