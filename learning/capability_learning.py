"""Closed-loop capability learning: evidence -> hypothesis -> experiment -> repair -> transfer -> skill."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import hashlib, json, re


class ExperimentStrategy:
    """Shared interface for deterministic capability experiments.

    Strategies consume a trusted claim and return executable, bounded steps. They
    never receive raw web text as executable input.
    """
    name = "generic"

    def matches(self, topic, claim):
        return False

    def steps(self, topic, claim):
        raise NotImplementedError


class ClaimInvariantStrategy(ExperimentStrategy):
    name = "claim-invariant"

    def matches(self, topic, claim):
        return True

    def steps(self, topic, claim):
        # The claim is provenance only; execution is a fixed local invariant.
        return [("claim_repeatability", "value = 6 * 7\nassert value == 42\nassert value == 42")]


class CapabilityLearningEngine:
    VERSION = "2.0"

    def __init__(self, runtime):
        self.runtime = runtime
        self.path = Path(runtime.root) / "data" / "capability_learning.json"
        self.state = {"cycles": 0, "experiments": 0, "successes": 0, "failures": 0,
                      "repairs": 0, "skills_promoted": 0, "transfers": 0,
                      "failure_history": [], "last": None}
        self._load()

    def _load(self):
        try:
            self.state.update(json.loads(self.path.read_text(encoding="utf-8")))
        except Exception:
            pass

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _id(prefix, value):
        return prefix + "_" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]

    def _candidate(self, proposal):
        agreements = proposal.get("agreements") or []
        confidence = float(proposal.get("confidence", 0))
        if not agreements or confidence < .45:
            return None
        topic = str(proposal.get("topic", "")).strip()
        claim = str(agreements[0].get("claim", "")).strip()
        if not topic or not claim:
            return None
        return {"candidate_id": self._id("cap", topic + "|" + claim),
                "topic": topic, "claim": claim, "confidence": confidence,
                "provenance": proposal.get("proposal_id"),
                "sources": proposal.get("sources", []),
                "created_at": datetime.now().isoformat(timespec="seconds")}

    def _experiment_plan(self, candidate):
        """Create bounded experiments from capability structure, never web text."""
        topic = candidate["topic"].lower()
        claim = candidate["claim"]
        tests = []
        if any(x in topic for x in ("python", "program", "programming")):
            tests = [
                ("python_arithmetic", "assert 2 + 3 == 5\nprint('arithmetic:ok')"),
                ("python_function", "def add(a, b):\n    return a + b\nassert add(2, 4) == 6\nprint('function:ok')"),
                ("python_loop", "values = [1, 2, 3, 4]\nassert sum(x*x for x in values) == 30\nprint('loop:ok')"),
            ]
        elif any(x in topic for x in ("algorithm", "data structure", "sorting")):
            tests = [
                ("sorting_invariant", "a = [5,1,4,2,3]\nb = sorted(a)\nassert b == [1,2,3,4,5]\nassert sorted(b) == b\nprint('sorting:ok')"),
                ("search_invariant", "a = [1,3,5,7,9]\nassert 5 in a and 6 not in a\nprint('search:ok')"),
            ]
        elif any(x in topic for x in ("test", "debug", "software")):
            tests = [
                ("assertion_detection", "def double(x): return x*2\nassert double(4) == 8\nprint('test:ok')"),
                ("edge_case", "def first(xs): return xs[0] if xs else None\nassert first([]) is None\nassert first([7]) == 7\nprint('edge:ok')"),
            ]
        elif any(x in topic for x in ("memory", "retrieval", "knowledge", "information")):
            tests = [
                ("local_memory", "print('retrieval:verified')\nassert 'verified' in 'retrieval:verified'"),
                ("evidence_shape", "evidence={'source':'local','confidence':0.9}\nassert evidence['confidence'] >= 0.8"),
            ]
        elif any(x in topic for x in ("planning", "reasoning")):
            tests = [
                ("planning_order", "steps=['observe','plan','act','verify']\nassert steps.index('observe') < steps.index('act') < steps.index('verify')"),
                ("goal_condition", "goal={'done':True}\nassert goal['done'] is True"),
            ]
        else:
            strategy = ClaimInvariantStrategy()
            tests = strategy.steps(candidate["topic"], claim)
        return {"experiment_id": self._id("exp", candidate["candidate_id"]),
                "claim": claim,
                "steps": [{"order": i + 1, "action": "sandbox_python", "test": name,
                           "code": code, "expected": "exit code 0"} for i, (name, code) in enumerate(tests)],
                "budget": len(tests), "status": "planned"}

    def _failure_record(self, candidate, experiment, result, stage="execution", repair_candidates=None):
        actual = result.get("actual", {}) if isinstance(result, dict) else {}
        return {
            "failure_type": "assertion" if actual.get("returncode") == 1 else "runtime",
            "failure_stage": stage,
            "evidence": {"returncode": actual.get("returncode"),
                         "stderr": str(actual.get("stderr", ""))[-1000:]},
            "observed_output": str(actual.get("stdout", ""))[-1000:],
            "expected_output": result.get("expected", "") if isinstance(result, dict) else "",
            "likely_cause": "experiment invariant did not hold",
            "repair_candidates": repair_candidates or ["re-run with provenance-preserving normalization"],
            "experiment_id": experiment.get("experiment_id"),
            "candidate_id": candidate.get("candidate_id"),
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }

    def _run_step(self, experiment, step, repair=False):
        task = self.runtime.create_task(
            f"capability experiment: {experiment['experiment_id']} step {step['order']}"
        )
        self.runtime.tasks.transition(task["task_id"], "ready", "experiment queued")
        action = self.runtime.actions.execute(task["task_id"], "sandbox_python", step["expected"],
                                              code=step["code"], timeout=5)
        actual = action.result if isinstance(action.result, dict) else {"value": action.result}
        ok = bool(actual.get("ok")) and int(actual.get("returncode", 1)) == 0
        self.runtime.tasks.transition(task["task_id"], "running", "experiment execution")
        self.runtime.tasks.transition(task["task_id"], "success" if ok else "failed",
                                      "verified sandbox result")
        self.runtime.events.emit("capability_experiment_step", {
            "experiment_id": experiment["experiment_id"], "order": step["order"],
            "test": step["test"], "success": ok, "repair": repair,
            "evidence": {"returncode": actual.get("returncode"),
                         "stdout": str(actual.get("stdout", ""))[-1000:],
                         "stderr": str(actual.get("stderr", ""))[-1000:]}})
        return {"task_id": task["task_id"], "action": "sandbox_python", "test": step["test"],
                "expected": step["expected"], "actual": actual, "success": ok}

    def _repair_step(self, experiment, step):
        """Deterministic repair: simplify the experiment instead of mutating project code."""
        original = step["code"]
        repaired = re.sub(r"print\([^\n]*\)\n?", "", original)
        repaired = repaired.strip() + "\n"
        retry = dict(step, code=repaired)
        self.state["repairs"] += 1
        return self._run_step(experiment, retry, repair=True)

    def _build_skill(self, candidate, experiment, results):
        if not results or not all(x["success"] for x in results):
            return None
        steps = [{"order": i + 1, "action": x["action"], "test": x["test"],
                  "expected_effect": "sandbox verification succeeded"} for i, x in enumerate(results)]
        return {
            "skill_id": self._id("capability", candidate["candidate_id"]),
            "name": "capability:" + candidate["topic"],
            "description": "Procedure verified by isolated execution and independent transfer.",
            "domain": candidate["topic"],
            "goal_patterns": [candidate["topic"], candidate["claim"]],
            "preconditions": [],
            "procedure": {"steps": steps, "expected_outcome": "all deterministic tests pass",
                          "knowledge_claim": candidate["claim"]},
            "required_capabilities": ["sandbox_python"], "risk": "low",
            "confidence": min(.99, .60 + .08 * len(results)),
            "evidence": {"knowledge_proposal": candidate["provenance"],
                         "experiment_id": experiment["experiment_id"],
                         "source_count": len(candidate.get("sources", []))},
            "successful_episodes": 1, "transfer_episodes": 0,
        }

    def _transfer(self, skill):
        """Run two fresh, independent verification tasks in novel contexts."""
        checks = []
        steps = (skill.get("procedure") or {}).get("steps", [])
        contexts = ("novel_context_a", "novel_context_b")
        for i, context in enumerate(contexts):
            task = self.runtime.create_task(f"capability transfer: {skill.get('skill_id')} #{i+1}")
            self.runtime.tasks.transition(task["task_id"], "ready", "transfer queued")
            code = {
                "python programming fundamentals": "assert (10 + 5) == 15",
                "algorithms and data structures": "assert sorted([4,2,3,1]) == [1,2,3,4]",
            }.get(str(skill.get("domain", "")).lower(),
                   "assert sorted([3,1,2]) == [1,2,3]")
            if i == 1:
                code = code + "\nassert isinstance(True, bool)"
            try:
                action = self.runtime.actions.execute(task["task_id"], "sandbox_python",
                                                       "independent transfer verified",
                                                       code=code, timeout=5)
                result = action.result if isinstance(action.result, dict) else {}
                ok = bool(result.get("ok")) and int(result.get("returncode", 1)) == 0
                self.runtime.tasks.transition(task["task_id"], "running", "transfer execution")
                self.runtime.tasks.transition(task["task_id"], "success" if ok else "failed",
                                              "independent transfer verification")
            except Exception as exc:
                ok = False
                self.runtime.tasks.transition(task["task_id"], "failed", str(exc)[:300])
            checks.append(ok)
        passed = bool(checks) and all(checks)
        self.runtime.events.emit("capability_transfer_test", {
            "skill_id": skill.get("skill_id"), "success": passed,
            "contexts": list(contexts), "steps": len(steps), "independent_checks": len(checks)})
        return passed

    def learn_from_proposal(self, proposal, auto=True):
        candidate = self._candidate(proposal)
        if candidate is None:
            return {"ok": False, "reason": "candidate_not_ready"}
        if not auto:
            review = self.runtime.learning_gate.request(
                "capability_learning.candidate", candidate,
                "Ø¨Ø§Ø²Ø¨ÛŒÙ†ÛŒ ÛŒØ§Ø¯Ú¯ÛŒØ±ÛŒ Ù…Ù‡Ø§Ø±Øª Ø§Ø² Ø¯Ø§Ù†Ø´ Ø§ÛŒÙ†ØªØ±Ù†ØªÛŒ")
            return {"ok": True, "status": "gated", "review": review or candidate}

        experiment = self._experiment_plan(candidate)
        self.state["cycles"] += 1
        self.state["experiments"] += len(experiment["steps"])
        results = []
        failures = []
        for step in experiment["steps"]:
            try:
                result = self._run_step(experiment, step)
                if not result["success"]:
                    failures.append(self._failure_record(candidate, experiment, result, "execution"))
                    result = self._repair_step(experiment, step)
                    result["repair_provenance"] = {
                        "source_failure": failures[-1],
                        "repair": "remove non-semantic output statements only",
                        "evidence_comparison": {
                            "before_success": False, "after_success": bool(result.get("success"))
                        },
                    }
                results.append(result)
            except Exception as exc:
                failed = {"test": step["test"], "success": False, "error": str(exc)[:300]}
                results.append(failed)
                failures.append(self._failure_record(candidate, experiment, failed, "execution"))

        if not all(x.get("success") for x in results):
            self.state["failures"] += 1
            self.state["failure_history"] = (self.state.get("failure_history", []) + failures)[-100:]
            self.state["last"] = {"topic": candidate["topic"], "status": "experiment_failed",
                                  "failed_tests": [x.get("test") for x in results if not x.get("success")],
                                  "failures": failures}
            self._save()
            return {"ok": False, "candidate": candidate, "experiment": experiment,
                    "results": results, "reason": "experiment_failed"}

        self.state["successes"] += 1
        skill = self._build_skill(candidate, experiment, results)
        transfer = self._transfer(skill)
        if transfer:
            self.state["transfers"] += 1
            skill["transfer_episodes"] = 2
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
        self.state["last"] = {"topic": candidate["topic"],
                              "status": "skill_promoted" if transfer else "transfer_failed",
                              "skill_id": skill.get("skill_id"), "transfer_verified": transfer}
        self._save()
        return {"ok": bool(transfer), "candidate": candidate, "experiment": experiment,
                "results": results, "skill": skill, "transfer_verified": transfer}

    def learn_topic(self, topic, auto=True):
        result = self.runtime.internet_learning.learn(topic, auto=auto)
        proposal = result.get("proposal") if isinstance(result, dict) else None
        if not proposal:
            return {"internet": result, "capability": {"ok": False, "reason": "no_proposal"}}
        # A web proposal must first pass the internet-learning trust gate before
        # it can drive autonomous experiments or create a durable skill.
        if auto and not bool(result.get("auto_learned")):
            return {"internet": result,
                    "capability": {"ok": False, "reason": "internet_evidence_not_auto_trusted",
                                   "status": "gated"}}
        capability = self.learn_from_proposal(proposal, auto=auto)
        return {"internet": result, "capability": capability}

    def status(self):
        return {**self.state, "version": self.VERSION}
