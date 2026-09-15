from __future__ import annotations

from datetime import datetime
from typing import Any


class RecoveryOrchestrator:
    """Keeps a long-horizon goal alive after a failed step without restarting it."""

    def __init__(self, runtime):
        self.runtime = runtime

    def _candidate_actions(self, step_title: str, primary: str) -> list[str]:
        title = str(step_title).lower()
        candidates = [primary]
        if any(x in title for x in ("شواهد", "بررسی", "inspect", "evidence")):
            candidates += ["project_files", "project_summary"]
        else:
            candidates += ["project_summary", "project_files"]
        return list(dict.fromkeys(candidates))

    def recover(self, goal: dict[str, Any], plan, state: dict[str, Any], failed_step: int) -> dict[str, Any]:
        step = next((s for s in plan.steps if s.id == int(failed_step)), None)
        if step is None:
            return {"recovered": False, "reason": "unknown_step"}

        primary = "project_summary"
        candidates = self._candidate_actions(step.title, primary)
        attempts = []
        chosen = None
        observation = None
        for index, action in enumerate(candidates):
            try:
                result = self.runtime.registry.run(action)
                verified = result is not None
            except Exception as exc:
                result = None
                verified = False
                error = str(exc)
            else:
                error = ""
            attempt = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "step": step.id,
                "action": action,
                "attempt": index + 1,
                "verified": verified,
            }
            if error:
                attempt["error"] = error
            attempts.append(attempt)
            if verified:
                chosen = action
                observation = result
                break

        if chosen is not None:
            plan = self.runtime.orchestrator.planner.replan(plan, failed_step, "recovered with alternate verified action")
            step = next(s for s in plan.steps if s.id == int(failed_step))
            step.status = "done"
            step.result = f"recovered via {chosen}"
            plan.status = "running" if any(s.status != "done" for s in plan.steps) else "complete"
            state["recovery_count"] = int(state.get("recovery_count", 0)) + 1
            state["last_recovery"] = attempts[-1]
            self.runtime.events.emit("goal_recovered", {
                "goal_id": goal.get("id"),
                "step": step.id,
                "action": chosen,
                "attempts": len(attempts),
            })
            return {
                "recovered": True,
                "action": chosen,
                "attempts": attempts,
                "observation": observation,
                "plan_version": plan.version,
            }

        state["last_recovery"] = attempts[-1] if attempts else None
        self.runtime.events.emit("goal_recovery_failed", {
            "goal_id": goal.get("id"),
            "step": step.id,
            "attempts": len(attempts),
        })
        return {"recovered": False, "attempts": attempts}
