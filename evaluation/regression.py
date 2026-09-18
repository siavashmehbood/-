"""Promotion gate for reproducible benchmark regression checks."""
from __future__ import annotations
import json
from pathlib import Path

class RegressionGate:
    def __init__(self, path=None, minimum_score=0.78):
        self.path = Path(path) if path else None
        self.minimum_score = float(minimum_score)
        self.baseline = None
        if self.path and self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.baseline = float(data.get("baseline", minimum_score))
            except Exception:
                self.baseline = None

    def evaluate(self, current_score, baseline_score=None):
        current = float(current_score)
        baseline = float(baseline_score if baseline_score is not None else (self.baseline if self.baseline is not None else self.minimum_score))
        return {"passed": current >= baseline, "current": current, "baseline": baseline,
                "delta": round(current - baseline, 4)}

    def can_promote(self, current_score, baseline_score=None):
        return bool(self.evaluate(current_score, baseline_score)["passed"])

    def record_baseline(self, score):
        self.baseline = float(score)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"baseline": self.baseline}, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.baseline
