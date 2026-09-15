from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path


class AutonomousGoalRunner:
    """Persistent bounded goal progression over safe, observable runtime actions."""

    def __init__(self, runtime, path: Path):
        self.runtime = runtime
        self.path = Path(path)
        if not self.path.is_absolute():
            self.path = Path(runtime.root) / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self):
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data):
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _action_for(self, title: str) -> str:
        t = str(title).lower()
        if any(x in t for x in ("شواهد", "بررسی", "جمع‌آوری", "وضعیت", "inspect", "evidence")):
            return "project_files"
        if any(x in t for x in ("اندازه", "ارزیابی", "مشاهده", "measure", "evaluate")):
            return "project_summary"
        return "project_summary"

    def advance(self, goal: dict, plan):
        data = self._load()
        key = str(goal.get("id"))
        state = data.get(key, {"goal_id": goal.get("id"), "goal": goal.get("title"), "step": 0, "history": []})
        step_index = int(state.get("step", 0))
        if step_index >= len(plan.steps):
            state["status"] = "completed"
            self._save({**data, key: state})
            return state, None

        step = plan.steps[step_index]
        action = self._action_for(step.title)
        observation = self.runtime.registry.run(action)
        verified = observation is not None
        event = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "step": step.id,
            "title": step.title,
            "action": action,
            "verified": verified,
        }
        state["history"].append(event)
        if verified:
            step.status = "done"
            step.result = "observable result received"
            state["step"] = step_index + 1
            state["status"] = "completed" if state["step"] >= len(plan.steps) else "running"
        else:
            step.status = "failed"
            state["status"] = "reassess"
        state["last"] = event
        self._save({**data, key: state})
        return state, observation

    def snapshot(self):
        return self._load()
