from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any


@dataclass
class SelfState:
    """Persistent metacognitive snapshot: what the runtime believes about itself."""
    capability: dict[str, float] = field(default_factory=dict)
    capability_domains: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.5
    uncertainty: list[str] = field(default_factory=list)
    active_goal: str = ""
    strategy: str = ""
    preferred_action: str = ""
    known_limits: list[str] = field(default_factory=list)
    recent_failures: int = 0
    recent_successes: int = 0
    calibration_error: float = 0.0
    self_assessment: str = "unknown"
    last_update: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    evaluation_weights: dict[str, dict[str, float]] = field(default_factory=lambda: {"prediction": {"prediction": .35, "evidence": .25, "agreement": .20, "calibration": .20}})


class SelfAwarenessEngine:
    """Persistent metacognition that can change future decisions and transfer experience."""

    DOMAIN_MAP = {
        "project_files": "perception",
        "project_summary": "understanding",
        "memory_search": "recall",
        "reason": "reasoning",
        "plan": "planning",
        "verify": "verification",
    }

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.state = SelfState()
        self.history: list[dict[str, Any]] = []
        self._load()

    def _load(self):
        if not self.path or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = SelfState(**data.get("state", {}))
            self.history = list(data.get("history", []))[-100:]
        except (OSError, ValueError, TypeError):
            self.state = SelfState()
            self.history = []

    def _save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"state": asdict(self.state), "history": self.history[-100:]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def observe(self, goal: str, action: str, score: float, verified: bool,
                expected: float | None = None, failure_reason: str = "") -> dict[str, Any]:
        score = max(0.0, min(1.0, float(score)))
        key = str(action)
        old = self.state.capability.get(key, 0.5)
        self.state.capability[key] = round(old * 0.7 + score * 0.3, 4)
        domain = self.DOMAIN_MAP.get(key, "execution")
        old_domain = self.state.capability_domains.get(domain, 0.5)
        self.state.capability_domains[domain] = round(old_domain * 0.7 + score * 0.3, 4)
        self.state.active_goal = str(goal)
        self.state.strategy = key
        if verified and score >= 0.7:
            self.state.recent_successes += 1
        else:
            self.state.recent_failures += 1
        if failure_reason and failure_reason not in self.state.uncertainty:
            self.state.uncertainty.append(str(failure_reason))
        if expected is not None:
            self.state.calibration_error = round(
                self.state.calibration_error * 0.7 + abs(float(expected) - score) * 0.3, 4
            )
        self.state.confidence = round(self._overall_confidence(), 4)
        self.state.self_assessment = self._self_assessment()
        self._update_limits()
        self.state.last_update = datetime.now().isoformat(timespec="seconds")
        event = {
            "goal": str(goal), "action": key, "domain": domain, "score": score,
            "verified": bool(verified), "expected": expected,
            "failure_reason": str(failure_reason), "confidence": self.state.confidence,
            "self_assessment": self.state.self_assessment, "time": self.state.last_update,
        }
        self.history.append(event)
        self.history = self.history[-100:]
        self._save()
        return event

    def _overall_confidence(self) -> float:
        if not self.state.capability_domains:
            return 0.5
        mean = sum(self.state.capability_domains.values()) / len(self.state.capability_domains)
        penalty = min(0.25, self.state.calibration_error)
        return max(0.0, min(1.0, mean - penalty))

    def _self_assessment(self) -> str:
        domains = self.state.capability_domains
        if not domains:
            return "unknown"
        mean = sum(domains.values()) / len(domains)
        weakest = min(domains, key=domains.get)
        if self.state.calibration_error > 0.25:
            return "poorly_calibrated"
        if mean >= 0.8:
            return "strong"
        if mean >= 0.6:
            return f"functional; weakest={weakest}"
        return f"limited; weakest={weakest}"

    def _update_limits(self):
        limits = list(self.state.known_limits)
        for domain, score in self.state.capability_domains.items():
            if score < 0.4:
                marker = f"low capability in {domain}"
                if marker not in limits:
                    limits.append(marker)
        self.state.known_limits = limits[-20:]

    def reassess(self, candidates: list[str]) -> list[str]:
        """Rank actions using capability, calibration and known limits."""
        unique = list(dict.fromkeys(str(x) for x in candidates))
        def utility(action: str) -> float:
            score = self.state.capability.get(action, 0.5)
            domain = self.DOMAIN_MAP.get(action, "execution")
            if f"low capability in {domain}" in self.state.known_limits:
                score -= 0.35
            if self.state.calibration_error > 0.25:
                score -= 0.05
            return score
        return sorted(unique, key=utility, reverse=True)

    def control_next_action(self, candidates: list[str]) -> dict[str, Any]:
        ranked = self.reassess(candidates)
        chosen = ranked[0] if ranked else "project_summary"
        self.state.preferred_action = chosen
        reason = "best known capability"
        if self.state.calibration_error > 0.25:
            reason = "best capability under low calibration confidence"
        self._save()
        return {
            "preferred_action": chosen,
            "ranked_actions": ranked,
            "reason": reason,
            "confidence": self.state.confidence,
            "calibration_error": self.state.calibration_error,
        }

    def transfer_score(self, goal: str, action: str) -> float:
        """Estimate capability for a new goal from action/domain experience."""
        key = str(action)
        direct = self.state.capability.get(key, 0.5)
        domain = self.DOMAIN_MAP.get(key, "execution")
        domain_score = self.state.capability_domains.get(domain, direct)
        related = [e for e in self.history if e.get("action") == key]
        if related:
            recent = sum(float(e.get("score", .5)) for e in related[-5:]) / min(5, len(related))
        else:
            recent = direct
        calibration_penalty = min(.2, self.state.calibration_error * .5)
        return round(max(0.0, min(1.0, direct * .45 + domain_score * .35 + recent * .20 - calibration_penalty)), 4)

    def transfer_control(self, goal: str, candidates: list[str]) -> dict[str, Any]:
        """Choose an action for a differently-worded/new goal using learned capability."""
        ranked = sorted(
            dict.fromkeys(str(x) for x in candidates),
            key=lambda action: self.transfer_score(goal, action),
            reverse=True,
        )
        chosen = ranked[0] if ranked else "project_summary"
        self.state.active_goal = str(goal)
        self.state.preferred_action = chosen
        score = self.transfer_score(goal, chosen)
        reason = "transferred capability from prior experience"
        if self.state.calibration_error > .25:
            reason = "transferred capability with verification required"
        self._save()
        return {"goal": str(goal), "preferred_action": chosen, "ranked_actions": ranked,
                "transfer_confidence": score, "reason": reason}

    def evaluate_action(self, goal: str, action: str, predicted_confidence: float = 0.5, evidence_confidence: float = 0.5, novelty: float = 0.0, reversibility: float = 0.8, safety: float = 1.0, verification_available: bool = True) -> dict[str, Any]:
        """Comprehensive pre-action metacognitive evaluation and control gate."""
        goal = str(goal); action = str(action)
        predicted = max(0.0, min(1.0, float(predicted_confidence)))
        evidence = max(0.0, min(1.0, float(evidence_confidence)))
        novelty = max(0.0, min(1.0, float(novelty)))
        reversibility = max(0.0, min(1.0, float(reversibility)))
        safety = max(0.0, min(1.0, float(safety)))
        capability = self.transfer_score(goal, action)
        domain = self.DOMAIN_MAP.get(action, "execution")
        domain_capability = self.state.capability_domains.get(domain, capability)
        calibration = max(0.0, min(1.0, 1.0 - self.state.calibration_error))
        failure_pressure = min(1.0, max(0, self.state.recent_failures - self.state.recent_successes) / 5.0)
        uncertainty_pressure = min(1.0, len(self.state.uncertainty) / 5.0)
        risk = ((1-capability)*.24 + (1-calibration)*.18 + (1-evidence)*.14 + novelty*.12 + failure_pressure*.10 + uncertainty_pressure*.06 + (1-reversibility)*.06 + (1-safety)*.10)
        risk = round(max(0.0, min(1.0, risk)), 4)
        confidence = round(max(0.0, min(1.0, capability*.35 + predicted*.25 + evidence*.15 + calibration*.15 + safety*.10)), 4)
        reasons = []
        if capability < .4: reasons.append("weak capability")
        if domain_capability < .4: reasons.append(f"weak domain capability: {domain}")
        if self.state.calibration_error > .25: reasons.append("poor calibration")
        if evidence < .45: reasons.append("insufficient evidence")
        if novelty > .65: reasons.append("high novelty")
        if failure_pressure > .4: reasons.append("recent failure pressure")
        if not verification_available: reasons.append("verification unavailable")
        if reversibility < .35: reasons.append("low reversibility")
        if safety < .8: reasons.append("elevated safety concern")
        if safety < .5 or capability < .05 or risk >= .82:
            decision = "avoid"
        elif not verification_available or risk >= .52 or capability < .4 or evidence < .45 or self.state.calibration_error > .25:
            decision = "gather_evidence"
        else:
            decision = "act"
        result = {
            "goal": goal, "action": action, "domain": domain,
            "capability": round(capability, 4), "domain_capability": round(domain_capability, 4),
            "predicted_confidence": round(predicted, 4), "evidence_confidence": round(evidence, 4),
            "calibration_confidence": round(calibration, 4), "novelty": round(novelty, 4),
            "failure_pressure": round(failure_pressure, 4), "uncertainty_pressure": round(uncertainty_pressure, 4),
            "reversibility": round(reversibility, 4), "safety": round(safety, 4),
            "verification_available": bool(verification_available), "risk": risk,
            "confidence": confidence, "decision": decision,
            "reasons": reasons or ["sufficient capability and evidence"],
            "time": datetime.now().isoformat(timespec="seconds"),
        }
        self.state.active_goal = goal
        self.state.strategy = action
        self.state.preferred_action = action if decision == "act" else ("project_files" if decision == "gather_evidence" else "")
        self._save()
        return result

    def evaluation_snapshot(self, candidates: list[str], goal: str = "") -> dict[str, Any]:
        """Evaluate all candidate actions and expose a decision matrix."""
        goal = str(goal or self.state.active_goal)
        evaluations = [self.evaluate_action(goal, action) for action in dict.fromkeys(candidates)]
        ranked = sorted(evaluations, key=lambda item: (item["decision"] != "act", item["risk"], -item["confidence"]))
        return {"goal": goal, "evaluations": ranked, "recommended": ranked[0] if ranked else None,
                "self_confidence": self.state.confidence, "calibration_error": self.state.calibration_error,
                "known_limits": list(self.state.known_limits)}

    def evaluate_plan(self, goal: str, steps: list[Any], predicted_confidence: float = .5, evidence_confidence: float = .5) -> dict[str, Any]:
        """Evaluate every plan step and identify the weakest link before execution."""
        evaluations = []
        for index, step in enumerate(steps):
            if isinstance(step, dict):
                action = step.get("action") or step.get("title") or "project_summary"
            else:
                action = str(step)
            evaluations.append(self.evaluate_action(
                goal, action, predicted_confidence, evidence_confidence,
                novelty=min(.9, index * .12), reversibility=.8, safety=1.0,
                verification_available=True,
            ))
        risks = [item["risk"] for item in evaluations]
        weakest = min(evaluations, key=lambda item: item["confidence"]) if evaluations else None
        total_risk = round(sum(risks) / len(risks), 4) if risks else .5
        decision = "avoid" if any(x["decision"] == "avoid" for x in evaluations) else (
            "gather_evidence" if any(x["decision"] == "gather_evidence" for x in evaluations) else "act"
        )
        return {"goal": str(goal), "steps": evaluations, "weakest_step": weakest,
                "total_risk": total_risk, "decision": decision,
                "plan_confidence": round(max(0.0, 1.0 - total_risk), 4)}

    def evaluate_outcome(self, evaluation: dict[str, Any], actual_score: float, verified: bool) -> dict[str, Any]:
        """Compare pre-action confidence with reality and expose calibration feedback."""
        actual = max(0.0, min(1.0, float(actual_score)))
        predicted = max(0.0, min(1.0, float(evaluation.get("confidence", .5))))
        error = round(abs(predicted - actual), 4)
        direction = "overconfident" if predicted > actual + .15 else (
            "underconfident" if actual > predicted + .15 else "calibrated"
        )
        learning_signal = round(max(0.0, min(1.0, actual - error - (0.2 if not verified else 0.0))), 4)
        return {"predicted": round(predicted, 4), "actual": round(actual, 4),
                "error": error, "verified": bool(verified),
                "learning_signal": learning_signal, "calibration_direction": direction}

    def evaluate_goal(self, goal: str, evidence_confidence=.5, novelty=.5, feasibility=.5, importance=.5, reversibility=.8, safety=1.0) -> dict[str, Any]:
        """Evaluate whether a goal itself is sufficiently understood and feasible before planning."""
        evidence=max(0.,min(1.,float(evidence_confidence))); novelty=max(0.,min(1.,float(novelty)))
        feasibility=max(0.,min(1.,float(feasibility))); importance=max(0.,min(1.,float(importance)))
        reversibility=max(0.,min(1.,float(reversibility))); safety=max(0.,min(1.,float(safety)))
        ambiguity=1.-evidence; risk=(ambiguity*.25+novelty*.2+(1-feasibility)*.25+(1-reversibility)*.1+(1-safety)*.2)
        confidence=max(0.,min(1.,evidence*.3+feasibility*.35+importance*.1+(1-novelty)*.1+reversibility*.05+safety*.1))
        decision='avoid' if safety<.5 or feasibility<.2 or risk>=.8 else ('clarify' if evidence<.35 or novelty>.8 else ('gather_evidence' if risk>=.5 else 'proceed'))
        reasons=[]
        if evidence<.35: reasons.append('goal poorly evidenced')
        if novelty>.8: reasons.append('goal highly novel')
        if feasibility<.4: reasons.append('goal feasibility is uncertain')
        if reversibility<.35: reasons.append('goal is hard to reverse')
        if safety<.8: reasons.append('goal has elevated safety concern')
        return {'goal':str(goal),'evidence_confidence':round(evidence,4),'novelty':round(novelty,4),'feasibility':round(feasibility,4),'importance':round(importance,4),'reversibility':round(reversibility,4),'safety':round(safety,4),'ambiguity':round(ambiguity,4),'risk':round(max(0.,min(1.,risk)),4),'confidence':round(confidence,4),'decision':decision,'reasons':reasons or ['goal sufficiently understood and feasible']}

    def evaluate_prediction(self, prediction_confidence=.5, evidence_confidence=.5, model_agreement=.5, novelty=.5, calibration=None) -> dict[str, Any]:
        """Evaluate the reliability of a prediction before allowing it to drive action."""
        p=max(0.,min(1.,float(prediction_confidence))); e=max(0.,min(1.,float(evidence_confidence)))
        agreement=max(0.,min(1.,float(model_agreement))); novelty=max(0.,min(1.,float(novelty)))
        cal=max(0.,min(1.,1.-(self.state.calibration_error if calibration is None else float(calibration))))
        weights=self.state.evaluation_weights.get("prediction", {})
        wp=float(weights.get("prediction", .35)); we=float(weights.get("evidence", .25))
        wa=float(weights.get("agreement", .20)); wc=float(weights.get("calibration", .20))
        total=max(.001,wp+we+wa+wc); wp,we,wa,wc=[x/total for x in (wp,we,wa,wc)]
        risk=(1-p)*wp+(1-e)*we+(1-agreement)*wa+novelty*.1+(1-cal)*wc
        confidence=max(0.,min(1.,p*wp+e*we+agreement*wa+cal*wc))
        decision='reject' if risk>=.7 else ('verify' if risk>=.35 else 'accept')
        return {'prediction_confidence':round(p,4),'evidence_confidence':round(e,4),'model_agreement':round(agreement,4),'novelty':round(novelty,4),'calibration_confidence':round(cal,4),'risk':round(risk,4),'confidence':round(confidence,4),'decision':decision}

    def calibration_update(self, predicted_confidence: float, actual_score: float, verified: bool=True) -> dict[str, Any]:
        """Persist a bounded calibration update from prediction error."""
        predicted=max(0.,min(1.,float(predicted_confidence))); actual=max(0.,min(1.,float(actual_score)))
        error=abs(predicted-actual); self.state.calibration_error=round(self.state.calibration_error*.8+error*.2,4)
        weights=dict(self.state.evaluation_weights.get("prediction", {}))
        if predicted > actual + .15:
            weights["prediction"]=min(.55, weights.get("prediction", .35)*.9)
            weights["evidence"]=min(.55, weights.get("evidence", .25)+.04)
            weights["agreement"]=min(.45, weights.get("agreement", .20)+.03)
        elif actual > predicted + .15:
            weights["prediction"]=min(.55, weights.get("prediction", .35)+.03)
            weights["evidence"]=max(.10, weights.get("evidence", .25)-.02)
        self.state.evaluation_weights["prediction"]=weights
        self.state.confidence=round(self._overall_confidence(),4); self.state.last_update=datetime.now().isoformat(timespec='seconds'); self._save()
        return {'predicted':round(predicted,4),'actual':round(actual,4),'error':round(error,4),'verified':bool(verified),'calibration_error':self.state.calibration_error,'confidence':self.state.confidence,'weights':dict(weights)}

    def introspect(self) -> dict[str, Any]:
        strongest = sorted(self.state.capability.items(), key=lambda x: x[1], reverse=True)
        weakest = sorted(self.state.capability.items(), key=lambda x: x[1])
        domains = sorted(self.state.capability_domains.items(), key=lambda x: x[1], reverse=True)
        return {
            "self_model": asdict(self.state),
            "strongest_capabilities": strongest[:3],
            "weakest_capabilities": weakest[:3],
            "strongest_domains": domains[:3],
            "weakest_domains": domains[-3:],
            "recent_events": self.history[-5:],
            "recommendation": self._recommendation(),
        }

    def _recommendation(self) -> str:
        if self.state.calibration_error > 0.25:
            return "reduce confidence and verify predictions before acting"
        if self.state.recent_failures > self.state.recent_successes:
            return "prefer previously successful alternatives and gather more evidence"
        if self.state.known_limits:
            return "avoid weak capabilities until more evidence improves them"
        return "continue current strategy while verifying outcomes"
