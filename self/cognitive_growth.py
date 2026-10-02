from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from persistence import atomic_write_json, load_critical_json


@dataclass
class Weakness:
    weakness_id: str
    capability: str
    failed_task: str
    expected_result: str
    actual_result: str
    failure_reason: str
    confidence: float
    recurrence_count: int
    evidence: list
    related_components: list
    related_knowledge: list
    related_skills: list
    proposed_learning_goal: str
    status: str = "open"


class WeaknessLedger:
    """Persistent evidence ledger for failures; it never changes code or approves learning."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = load_critical_json(self.path, [], validator=lambda x: isinstance(x, list))
        self.rows = rows if isinstance(rows, list) else []

    @staticmethod
    def _id(capability: str, failed_task: str, reason: str) -> str:
        raw = "|".join((capability.strip().lower(), failed_task.strip().lower(), reason.strip().lower()))
        return "weak_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def record(self, *, capability: str, failed_task: str, expected_result: str,
               actual_result: str, failure_reason: str, confidence: float,
               evidence: list | None = None, related_components: list | None = None,
               related_knowledge: list | None = None, related_skills: list | None = None,
               proposed_learning_goal: str = "") -> dict:
        wid = self._id(capability, failed_task, failure_reason)
        existing = next((r for r in self.rows if r.get("weakness_id") == wid), None)
        if existing:
            existing["recurrence_count"] = int(existing.get("recurrence_count", 1)) + 1
            existing["confidence"] = max(float(existing.get("confidence", 0)), float(confidence))
            existing["evidence"] = list(dict.fromkeys(list(existing.get("evidence", [])) + list(evidence or [])))
            existing["updated_at"] = datetime.now().isoformat(timespec="seconds")
            self._save()
            return dict(existing)
        row = asdict(Weakness(
            wid, str(capability), str(failed_task), str(expected_result), str(actual_result),
            str(failure_reason), max(0.0, min(1.0, float(confidence))), 1,
            list(evidence or []), list(related_components or []), list(related_knowledge or []),
            list(related_skills or []), str(proposed_learning_goal or capability), "open"))
        row["created_at"] = datetime.now().isoformat(timespec="seconds")
        row["updated_at"] = row["created_at"]
        self.rows.append(row)
        self._save()
        return dict(row)

    def mission(self, weakness_id: str, *, min_confidence: float = .5) -> dict | None:
        row = next((r for r in self.rows if r.get("weakness_id") == weakness_id), None)
        if not row or row.get("status") not in {"open", "remediation"}:
            return None
        if float(row.get("confidence", 0)) < min_confidence:
            return None
        return {
            "mission_id": "mission_" + weakness_id.removeprefix("weak_"),
            "weakness_id": weakness_id,
            "capability": row["capability"],
            "goal": row["proposed_learning_goal"],
            "evidence": list(row.get("evidence", [])),
            "status": "proposed",
            "requires_reviewer": True,
            "requires_human_approval": True,
        }

    def mark(self, weakness_id: str, status: str) -> dict | None:
        if status not in {"open", "learning", "retest", "remediation", "resolved"}:
            raise ValueError("invalid weakness status")
        row = next((r for r in self.rows if r.get("weakness_id") == weakness_id), None)
        if row:
            row["status"] = status
            row["updated_at"] = datetime.now().isoformat(timespec="seconds")
            self._save()
            return dict(row)
        return None

    def _save(self):
        atomic_write_json(self.path, self.rows)


class CapabilityBenchmark:
    """Measures public behavior before/after learning without training on evaluation cases."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state = load_critical_json(self.path, {"runs": []}, validator=lambda x: isinstance(x, dict))
        self.state = state if isinstance(state, dict) else {"runs": []}
        self.state.setdefault("runs", [])

    def run(self, capability: str, cases: list[dict], solver: Callable[[str], Any],
            evaluator: Callable[[Any, dict], bool], phase: str) -> dict:
        if phase not in {"baseline", "post_learning", "restart"}:
            raise ValueError("invalid benchmark phase")
        results = []
        for case in cases:
            output = solver(str(case["input"]))
            passed = bool(evaluator(output, case))
            results.append({"case_id": str(case["case_id"]), "passed": passed, "output": str(output)[:2000]})
        score = sum(r["passed"] for r in results)
        run = {
            "run_id": "bench_" + hashlib.sha256(
                json.dumps([capability, phase, [r["case_id"] for r in results], datetime.now().isoformat()],
                           ensure_ascii=False).encode("utf-8")).hexdigest()[:16],
            "capability": capability, "phase": phase, "score": score, "total": len(results),
            "results": results, "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.state["runs"].append(run)
        atomic_write_json(self.path, self.state)
        return dict(run)

    def compare(self, before: dict, after: dict) -> dict:
        if before.get("capability") != after.get("capability"):
            raise ValueError("capability mismatch")
        if int(before.get("total", 0)) != int(after.get("total", 0)):
            raise ValueError("benchmark size mismatch")
        before_ids = [str(r.get("case_id")) for r in before.get("results", [])]
        after_ids = [str(r.get("case_id")) for r in after.get("results", [])]
        if before_ids != after_ids:
            raise ValueError("case identity mismatch")
        delta = int(after.get("score", 0)) - int(before.get("score", 0))
        return {
            "capability": before["capability"], "before": before["score"], "after": after["score"],
            "total": before["total"], "delta": delta, "improved": delta > 0,
            "mastery_eligible": delta > 0 and int(after.get("score", 0)) > int(before.get("score", 0)),
            "next": "keep" if delta > 0 else "remediate",
        }


class CognitiveGrowthCycle:
    """Coordinates measurement and weakness state; approval remains owned by existing governance."""

    def __init__(self, root: str | Path):
        root = Path(root)
        self.weaknesses = WeaknessLedger(root / "data" / "weaknesses.json")
        self.benchmark = CapabilityBenchmark(root / "data" / "capability_benchmarks.json")

    def evaluate_failure(self, capability: str, task: str, expected: str, actual: str,
                         reason: str, evidence: list | None = None, confidence: float = .8) -> dict:
        weakness = self.weaknesses.record(
            capability=capability, failed_task=task, expected_result=expected,
            actual_result=actual, failure_reason=reason, confidence=confidence,
            evidence=evidence or [], proposed_learning_goal=f"Improve {capability}: {reason}")
        return {"weakness": weakness, "mission": self.weaknesses.mission(weakness["weakness_id"])}

    def begin_learning(self, weakness_id: str) -> dict | None:
        return self.weaknesses.mark(weakness_id, "learning")

    def begin_retest(self, weakness_id: str) -> dict | None:
        row = next((r for r in self.weaknesses.rows if r.get("weakness_id") == weakness_id), None)
        if not row or row.get("status") != "learning":
            return None
        return self.weaknesses.mark(weakness_id, "retest")

    def conclude(self, weakness_id: str, before: dict, after: dict) -> dict:
        row = next((r for r in self.weaknesses.rows if r.get("weakness_id") == weakness_id), None)
        if not row or row.get("status") != "retest":
            raise ValueError("weakness must be in retest before conclusion")
        comparison = self.benchmark.compare(before, after)
        status = "resolved" if comparison["mastery_eligible"] else "remediation"
        self.weaknesses.mark(weakness_id, status)
        return {"comparison": comparison, "weakness_status": status}
