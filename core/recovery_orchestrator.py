from __future__ import annotations

from datetime import datetime
from typing import Any


class RecoveryOrchestrator:
    """Recover a failed goal step using persistent local experience."""

    def __init__(self, runtime):
        self.runtime = runtime

    def _candidates(self, step_title: str, primary: str) -> list[str]:
        title = str(step_title).lower()
        candidates = [primary]
        if any(x in title for x in ("شواهد", "بررسی", "inspect", "evidence")):
            candidates += ["project_files", "project_summary"]
        else:
            candidates += ["project_summary", "project_files"]
        return list(dict.fromkeys(candidates))

    def _rank(self, goal, candidates):
        """Prefer actions with good local history and penalize repeated failures."""
        learning = getattr(self.runtime, "learning", None)
        if learning is None:
            return candidates
        try:
            from core.learned_action_ranker import LearnedActionRanker
            return LearnedActionRanker(learning).rank(goal.get("title", ""), candidates)
        except Exception:
            return candidates

    def recover(self, goal: dict[str, Any], plan, state: dict[str, Any], failed_step: int) -> dict[str, Any]:
        step = next((s for s in plan.steps if s.id == int(failed_step)), None)
        if step is None:
            return {"recovered": False, "reason": "unknown_step"}

        candidates = self._candidates(step.title, "project_summary")
        candidates = self._rank(goal, candidates)
        attempts = []
        chosen = None
        observation = None
        for index, action in enumerate(candidates):
            try:
                result = self.runtime.registry.run(action)
                verified = result is not None
                error = ""
            except Exception as exc:
                result = None
                verified = False
                error = str(exc)
            attempts.append({
                "time": datetime.now().isoformat(timespec="seconds"),
                "step": step.id,
                "action": action,
                "attempt": index + 1,
                "verified": verified,
                **({"error": error} if error else {}),
            })
            if verified:
                chosen, observation = action, result
                break

        learning = getattr(self.runtime, "learning", None)
        if learning is not None:
            for item in attempts:
                try:
                    learning.record(
                        goal.get("title", ""), item["action"],
                        "verified" if item["verified"] else "failed recovery attempt",
                        .9 if item["verified"] else .2,
                        strategy="recovery",
                        domain="autonomous-goal",
                    )
                except Exception:
                    pass

        if chosen is not None:
            plan = self.runtime.orchestrator.planner.replan(plan, failed_step, "recovered with learned action ranking")
            step.status = "done"
            step.result = f"recovered via {chosen}"
            plan.status = "running" if any(s.status != "done" for s in plan.steps) else "complete"
            state["recovery_count"] = int(state.get("recovery_count", 0)) + 1
            state["last_recovery"] = attempts[-1]
            self.runtime.events.emit("goal_recovered", {"goal_id": goal.get("id"), "step": step.id, "action": chosen, "attempts": len(attempts)})
            return {"recovered": True, "action": chosen, "attempts": attempts, "observation": observation, "plan_version": plan.version}

        state["last_recovery"] = attempts[-1] if attempts else None
        self.runtime.events.emit("goal_recovery_failed", {"goal_id": goal.get("id"), "step": step.id, "attempts": len(attempts)})
        return {"recovered": False, "attempts": attempts}
