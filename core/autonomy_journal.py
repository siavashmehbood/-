from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path


class AutonomyJournal:
    """Persistent, user-visible decision summaries; never stores private chain-of-thought."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, report: dict):
        entry = {
            "time": report.get("time", datetime.now().isoformat(timespec="seconds")),
            "cycle": report.get("cycle"),
            "goal": (report.get("selected") or {}).get("goal"),
            "reason": (report.get("selected") or {}).get("reason"),
            "priority": (report.get("selected") or {}).get("score"),
            "signals": [s.get("kind") for s in report.get("signals", [])],
            "action": (report.get("decision") or {}).get("action"),
            "confidence": (report.get("decision") or {}).get("prediction_confidence"),
            "verified": bool(report.get("verified")),
            "lesson": (report.get("reflection") or {}).get("lessons", [])[:2],
            "learning": report.get("learning"),
            "curriculum_learning": report.get("curriculum_learning"),
        }
        rows = self.read()
        rows.append(entry)
        self.path.write_text(json.dumps(rows[-1000:], ensure_ascii=False, indent=2), encoding="utf-8")
        return entry

    def read(self):
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def summary(self):
        rows = self.read()
        if not rows:
            return {"cycles": 0, "verified": 0, "success_rate": 0.0, "last": None}
        verified = sum(bool(x.get("verified")) for x in rows)
        return {
            "cycles": len(rows),
            "verified": verified,
            "success_rate": round(verified / len(rows), 3),
            "last": rows[-1],
        }
