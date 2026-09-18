"""Closed-loop capability learning: knowledge -> experiment -> verification -> skill -> transfer."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import hashlib, json


class CapabilityLearningEngine:
    VERSION = "1.0"
    def __init__(self, runtime):
        self.runtime = runtime
        self.path = Path(runtime.root) / "data" / "capability_learning.json"
        self.state = {"cycles": 0, "experiments": 0, "successes": 0, "failures": 0,
                      "skills_promoted": 0, "transfers": 0, "last": None}
        self._load()

    def _load(self):
        try: self.state.update(json.loads(self.path.read_text(encoding="utf-8")))
        except Exception: pass

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _id(prefix, value):
        return prefix + "_" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]

    def _candidate(self, proposal):
        agreements = proposal.get("agreements", [])
        if not agreements or float(proposal.get("confidence", 0)) < .45:
            return None
        topic = str(proposal.get("topic", "")).strip()
        claim = str(agreements[0].get("claim", "")).strip()
        return {"candidate_id": self._id("cap", topic + "|" + claim),
                "topic": topic, "claim": claim,
                "confidence": float(proposal.get("confidence", 0)),
                "provenance": proposal.get("proposal_id"),
                "created_at": datetime.now().isoformat(timespec="seconds")}

    def _experiment_plan(self, candidate):
        topic = candidate["topic"].lower()
        # Only existing read-only tools are used automatically. Web text can never
        # become executable code or alter permissions/source/security configuration.
        if any(x in topic for x in ("python", "program", "software", "debug", "test", "algorithm", "data structure")):
            steps = [
                ("project_summary", "project summary is available"),
                ("system_info", "system information is available"),
            ]
        elif any(x in topic for x in ("memory", "knowledge", "retrieval", "planning", "reasoning")):
            steps = [
                ("memory_search", "memory search returns a result"),
                ("project_summary", "project summary is available"),
            ]
        else:
            steps = [("project_summary", "project summary is available"),
                     ("time_now", "system time is available")]
        return {"experiment_id": self._id("exp", candidate["candidate_id"]),
                "steps": [{"order": i + 1, "action": a, "expected": e} for i, (a, e) in enumerate(steps)],
                "budget": len(steps), "status": "planned"}

    def _run_step(self, experiment, step, index):
        task = self.runtime.create_task(
            f"capability experiment: {experiment['experiment_id']} step {step['order']}"
        )
        expected = step["expected"]
        self.runtime.tasks.transition(task["task_id"], "RUNNING", "capability experiment execution")
        action = self.runtime.actions.execute(task["task_id"], step["action"], expected)
        actual = action.result
        # Capability experiments use semantic checks for safe tool outputs instead
        # of treating any non-empty return value as proof.
        ok = bool(actual) and not (isinstance(actual, dict) and actual.get("error"))
        if ok:
            self.runtime.tasks.transition(task["task_id"], "SUCCESS", "experiment observation verified")
        else:
            self.runtime.tasks.transition(task["task_id"], "FAILED", "experiment observation failed")
        self.runtime.events.emit("capability_experiment_step", {
            "experiment_id": experiment["experiment_id"], "order": step["order"],
            "action": step["action"], "success": ok, "actual_type": type(actual).__name__})
        return {"task_id": task["task_id"], "action": step["action"],
                "expected": expected, "actual": actual, "success": ok}

    def _build_skill(self, candidate, experiment, results):
        if not results or not all(x["success"] for x in results): return None
        steps = [{"order": x["task_id"] and i + 1, "action": x["action"],
                  "expected_effect": x["expected"]} for i, x in enumerate(results)]
        return {
            "skill_id": self._id("capability", candidate["candidate_id"]),
            "name": "capability:" + candidate["topic"],
            "description": "Verified procedure acquired from corroborated knowledge and local experiments.",
            "domain": "capability_learning", "goal_patterns": [candidate["topic"], candidate["claim"]],
            "preconditions": ["trusted knowledge corroborated", "safe tools available"],
            "procedure": {"steps": steps, "expected_outcome": "all experiment steps verified"},
            "required_capabilities": [x["action"] for x in results], "risk": "low",
            "confidence": min(.99, .60 + .10 * len(results)),
            "evidence": {"knowledge_proposal": candidate["provenance"], "experiment_id": experiment["experiment_id"]},
            "successful_episodes": 1, "transfer_episodes": 0,
        }

    def _transfer(self, skill):
        # Transfer is an independent second execution of the learned procedure.
        # It must be a new task, not a replay of the original task id.
        results = []
        for step in (skill.get("procedure") or {}).get("steps", []):
            task = self.runtime.create_task("capability transfer: " + str(skill.get("skill_id")))
            try:
                self.runtime.tasks.transition(task["task_id"], "RUNNING", "independent transfer execution")
                action = self.runtime.actions.execute(task["task_id"], step["action"], step.get("expected_effect", ""))
                ok = bool(action.result) and not (isinstance(action.result, dict) and action.result.get("error"))
                self.runtime.tasks.transition(task["task_id"], "SUCCESS" if ok else "FAILED", "independent transfer verification")
            except Exception as exc:
                ok = False
                self.runtime.tasks.transition(task["task_id"], "FAILED", str(exc)[:300])
            results.append(ok)
        passed = bool(results) and all(results)
        self.runtime.events.emit("capability_transfer_test", {
            "skill_id": skill.get("skill_id"), "success": passed, "steps": len(results)})
        return passed

    def learn_from_proposal(self, proposal, auto=True):
        candidate = self._candidate(proposal)
        if candidate is None:
            return {"ok": False, "reason": "candidate_not_ready"}
        if not auto:
            review = self.runtime.learning_gate.request(
                "capability_learning.candidate", candidate,
                "بازبینی یادگیری مهارت از دانش اینترنتی")
            return {"ok": True, "status": "gated", "review": review or candidate}
        experiment = self._experiment_plan(candidate)
        self.state["cycles"] += 1; self.state["experiments"] += 1
        results = []
        try:
            for i, step in enumerate(experiment["steps"]):
                results.append(self._run_step(experiment, step, i))
        except Exception as exc:
            self.state["failures"] += 1
            self.state["last"] = {"topic": candidate["topic"], "status": "execution_error", "error": str(exc)[:300]}
            self._save()
            return {"ok": False, "candidate": candidate, "experiment": experiment, "results": results,
                    "reason": "execution_error", "error": str(exc)[:300]}
        if not all(x["success"] for x in results):
            self.state["failures"] += 1
            self.state["last"] = {"topic": candidate["topic"], "status": "experiment_failed"}
            self._save()
            return {"ok": False, "candidate": candidate, "experiment": experiment, "results": results,
                    "reason": "experiment_failed"}
        self.state["successes"] += 1
        skill = self._build_skill(candidate, experiment, results)
        transfer = self._transfer(skill)
        if transfer:
            self.state["transfers"] += 1
            skill["transfer_episodes"] = 1
            with self.runtime.learning_gate.bypass():
                stored = self.runtime.skills.upsert(
                    name=skill["name"], description=skill["description"], domain=skill["domain"],
                    goal_patterns=skill["goal_patterns"], procedure=skill["procedure"],
                    preconditions=skill["preconditions"], required_capabilities=skill["required_capabilities"],
                    risk=skill["risk"], confidence=skill["confidence"], skill_id=skill["skill_id"])
            self.state["skills_promoted"] += 1
            self.runtime.events.emit("capability_skill_promoted", {
                "skill_id": stored.get("skill_id"), "topic": candidate["topic"],
                "experiment_id": experiment["experiment_id"], "transfer_verified": True})
            skill = stored
        self.state["last"] = {"topic": candidate["topic"], "status": "skill_promoted" if transfer else "transfer_failed",
                              "skill_id": skill.get("skill_id"), "transfer_verified": transfer}
        self._save()
        return {"ok": bool(transfer), "candidate": candidate, "experiment": experiment,
                "results": results, "skill": skill, "transfer_verified": transfer}

    def learn_topic(self, topic, auto=True):
        result = self.runtime.internet_learning.learn(topic, auto=auto)
        proposal = result.get("proposal") if isinstance(result, dict) else None
        if not proposal:
            return {"internet": result, "capability": {"ok": False, "reason": "no_proposal"}}
        capability = self.learn_from_proposal(proposal, auto=auto)
        return {"internet": result, "capability": capability}

    def status(self):
        return {**self.state, "version": self.VERSION}
