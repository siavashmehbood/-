from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class GeneralizedLesson:
    goal_pattern: str
    strategy: str
    confidence: float
    support: int
    context: dict

class GeneralizationEngine:
    """Deterministic context-aware transfer over local learning evidence."""
    def __init__(self, learning): self.learning = learning
    def generalize(self, goal, intent="general", domain="general", limit=5):
        rows = self.learning.semantic_lessons(goal, intent, domain, max(10, limit * 3))
        groups = {}
        for row in rows:
            key = (row.get("strategy","default"), row.get("domain",domain))
            groups.setdefault(key, []).append(row)
        out = []
        for (strategy, row_domain), items in groups.items():
            mean = sum(float(x.get("score",0)) for x in items) / len(items)
            conf = min(.95, .45 + .06 * len(items) + abs(mean-.5)*.3)
            out.append(GeneralizedLesson(str(goal), strategy, round(conf,3), len(items),
                                         {"intent":intent,"domain":row_domain,"mean_score":round(mean,3)}))
        return sorted(out, key=lambda x:(x.confidence,x.support), reverse=True)[:limit]
    def recommend(self, goal, intent="general", domain="general"):
        rows=self.generalize(goal,intent,domain,5)
        return rows[0].strategy if rows else self.learning.recommended_strategy(goal,intent,domain)
