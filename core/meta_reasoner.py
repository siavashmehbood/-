"""Deterministic meta-reasoning over method choice and reasoning evidence."""
from __future__ import annotations

class MetaReasoner:
    """Evaluate reasoning method from observable evidence; no external model."""
    METHODS = ("evidence-first", "reuse-learned-strategy", "increase-evidence", "change-strategy")

    def evaluate(self, *, uncertainty=1.0, success_rate=0.0, failure_count=0, strategy=None):
        uncertainty = max(0.0, min(1.0, float(uncertainty)))
        success_rate = max(0.0, min(1.0, float(success_rate)))
        failure_count = max(0, int(failure_count))
        if failure_count >= 2 or success_rate < 0.55:
            method = "change-strategy"
        elif uncertainty >= 0.65:
            method = "increase-evidence"
        elif success_rate >= 0.75 and strategy:
            method = "reuse-learned-strategy"
        else:
            method = "evidence-first"
        return {"method": method, "confidence": round(1.0 - uncertainty * 0.5, 3),
                "success_rate": round(success_rate, 3), "failure_count": failure_count,
                "strategy": strategy, "reason": "deterministic-evidence-policy"}

    def review(self, reasoning, outcome=None):
        outcome = outcome or {}
        evidence = reasoning.get("evidence_inference", {}) if isinstance(reasoning, dict) else {}
        return self.evaluate(uncertainty=evidence.get("uncertainty", 1.0),
                             success_rate=outcome.get("success_rate", 0.0),
                             failure_count=outcome.get("failure_count", 0),
                             strategy=outcome.get("strategy"))
