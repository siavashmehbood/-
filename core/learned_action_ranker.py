from __future__ import annotations

from collections import defaultdict


class LearnedActionRanker:
    """Ranks safe recovery actions from persisted LearningEngine experience."""

    def __init__(self, learning):
        self.learning = learning

    def rank(self, goal: str, actions: list[str]) -> list[str]:
        candidates = list(dict.fromkeys(str(x) for x in actions))
        try:
            rows = self.learning.semantic_lessons(goal, limit=100)
        except Exception:
            return candidates
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
            scored.append((score, -index, action))
        scored.sort(reverse=True)
        return [action for _, _, action in scored]
