from __future__ import annotations

from collections import defaultdict


class LearnedActionRanker:
    """Ranks safe recovery actions from persisted LearningEngine experience."""

    def __init__(self, learning):
        self.learning = learning

    def scores(self, goal: str, actions: list[str]) -> list[dict]:
        """Return explainable learned scores; this is a bounded learned core, not an executor."""
        candidates = list(dict.fromkeys(str(x) for x in actions))
        try:
            rows = self.learning.semantic_lessons(goal, limit=100)
        except Exception:
            return [{"action": action, "score": .5, "evidence_count": 0, "learned": False}
                    for action in candidates]
        stats = defaultdict(list)
        for row in rows:
            action = str(row.get("action", ""))
            if action in candidates:
                stats[action].append(float(row.get("score", 0)))
        scored = []
        for index, action in enumerate(candidates):
            values = stats.get(action, [])
            if values:
                mean = sum(values) / len(values)
                score = mean + min(.15, len(values) * .03)
            else:
                score = .5
            scored.append({"action": action, "score": round(score, 4),
                           "evidence_count": len(values), "learned": bool(values),
                           "_order": index})
        scored.sort(key=lambda row: (row["score"], -row["_order"]), reverse=True)
        for row in scored:
            row.pop("_order", None)
        return scored

    def rank(self, goal: str, actions: list[str]) -> list[str]:
        return [row["action"] for row in self.scores(goal, actions)]
