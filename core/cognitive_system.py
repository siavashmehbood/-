from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pathlib import Path

from core.cognitive_pipeline import CognitivePipeline
from core.grounded_synthesizer import GroundedSynthesizer
from core.self_correction import SelfCorrectionEngine


@dataclass(frozen=True)
class CognitiveComponents:
    dialogue: Any
    pipeline: CognitivePipeline
    memory: Any
    knowledge: Any
    learning: Any
    reasoning: Any
    planning: Any
    verification: Any
    autonomy: Any
    improvement: Any
    self_directed_learning: Any
    trusted_knowledge: Any
    learning_gate: Any


class CognitiveSystem:
    """Single composition root for the local IRAN cognitive architecture.

    Existing subsystems remain independently testable, but normal execution enters
    through this object so memory, reasoning, planning, verification, learning and
    improvement share one runtime-owned dependency graph.
    """

    VERSION = "2.0-cognitive-os"

    def __init__(self, runtime: Any):
        self.runtime = runtime
        self.dialogue = runtime.dialogue
        self.pipeline = self._get_pipeline()
        if getattr(self.dialogue, "grounded_synthesizer", None) is None:
            self.dialogue.grounded_synthesizer = GroundedSynthesizer(
                getattr(runtime, "knowledge", None), getattr(runtime, "memory", None),
                getattr(runtime, "learning", None))
        if getattr(self.pipeline, "self_correction", None) is None:
            self.pipeline.self_correction = SelfCorrectionEngine(
                Path(runtime.root) / "data" / "self_corrections.json")
        self.components = CognitiveComponents(
            dialogue=self.dialogue,
            pipeline=self.pipeline,
            memory=getattr(runtime, "memory", None),
            knowledge=getattr(runtime, "knowledge", None),
            learning=getattr(runtime, "learning", None),
            reasoning=getattr(self.pipeline, "reasoning_planning", None),
            planning=getattr(getattr(self.dialogue, "planner", None), "plan", None),
            verification=getattr(self.pipeline, "semantic_verifier", None),
            autonomy=getattr(runtime, "autonomous_supervisor", None)
            or getattr(runtime, "autonomy", None),
            improvement=getattr(runtime, "improvement", None),
            self_directed_learning=getattr(runtime, "self_directed_learning", None),
            trusted_knowledge=getattr(runtime, "trusted_knowledge", None),
            learning_gate=getattr(runtime, "learning_gate", None),
        )
        self.last_answer = ""
        self.last_trace = None
        self.last_output = {}

    def _get_pipeline(self) -> CognitivePipeline:
        pipeline = getattr(self.dialogue, "cognitive_pipeline", None)
        if isinstance(pipeline, CognitivePipeline):
            return pipeline
        pipeline = CognitivePipeline(self.dialogue)
        self.dialogue.cognitive_pipeline = pipeline
        self.dialogue._canonical_pipeline = pipeline
        return pipeline

    def dispatch(self, text: str) -> str:
        """Single ingress for every user interaction.

        Commands and natural language now enter the same CognitiveSystem boundary.
        Command execution remains a runtime adapter, while all natural language uses
        the canonical cognitive pipeline. This prevents parallel public entry paths.
        """
        clean_text = str(text or "").strip()
        if not clean_text:
            return "چیزی برای پردازش دریافت نکردم."
        if clean_text.startswith("/"):
            handler = getattr(self.runtime, "_handle_command", None)
            if callable(handler):
                result = handler(clean_text)
                self.last_answer = str(result)
                self.last_trace = getattr(self.dialogue, "last_trace", None)
                self.last_output = self.unified_output()
                return str(result)
        return self.turn(clean_text)

    def turn(self, text: str) -> str:
        """Canonical natural-language turn: perceive -> reason -> act -> verify -> learn."""
        try:
            self.runtime.world.record_observation("user_input", str(text), .85, source="canonical_turn")
        except Exception:
            pass
        answer = self.pipeline.run(text)
        self.last_answer = answer
        self.last_trace = getattr(self.dialogue, "last_trace", None)
        self._post_turn_learning(text, answer, self.last_trace)
        self.last_output = self.unified_output()
        return answer

    def _post_turn_learning(self, text: str, answer: str, trace: Any) -> dict:
        """Evaluate meaningful learning opportunities after every canonical turn."""
        loop = getattr(self.runtime, "effect_learning", None)
        learning = getattr(self.runtime, "learning", None)
        if loop is None or learning is None or trace is None:
            return {}
        try:
            intent = getattr(trace, "intent", "general") or "general"
            feedback_turn = getattr(trace, "answer_status", "") == "FEEDBACK"
            if feedback_turn:
                previous = ""
                for row in reversed(self.runtime.memory.recent(80)):
                    if isinstance(row, (tuple, list)) and len(row) >= 3 and row[0] == "user":
                        candidate = str(row[1]).strip()
                        if candidate and candidate != str(text).strip():
                            previous = candidate
                            break
                goal = previous or str(getattr(trace, "topic", "") or "last_answer")
                effect = loop.evaluate(
                    goal, "explicit-feedback", str(text),
                    "پاسخ قبلی باید با بازخورد مثبت کاربر تأیید شود",
                    {"verified": True, "score": 0.98, "effect_observed": True},
                    strategy="feedback", domain="conversation",
                    episode_id=str(getattr(trace, "cycle_id", "") or ""), attempt=1)
                self.runtime.events.emit("learning_effect_evaluated", {
                    "goal": goal, "action": "explicit-feedback", "strategy": "feedback",
                    "effect": effect, "canonical": True,
                })
                return {"action": "feedback_validation", "effect": effect}
            goal = f"{intent}:{getattr(trace, 'topic', '') or 'conversation'}"
            confidence = float(getattr(trace, "confidence", 0.0) or 0.0)
            priority = loop.learning_priority(
                goal, getattr(trace, "intent", "general") or "general",
                "dialogue", uncertainty=max(0.0, 1.0-confidence),
                novelty=0.6 if not learning.adapt(goal, getattr(trace, "intent", "general") or "general", "dialogue").get("learned_rules") else 0.0)
            action = priority.get("action", "observe_and_wait")
            # Normal turns are observations, not learning evidence. Only an explicit
            # active experiment or a verified historical reuse is allowed to mutate
            # effect-learning state. This prevents routine PASS answers from earning
            # XP or becoming fake training samples.
            if action not in ("active_experiment", "reuse_best_then_verify"):
                observation = loop.observe_behavior(
                    goal, answer, strategy="baseline", domain="dialogue",
                    episode_id=str(getattr(trace, "cycle_id", "") or ""),
                    learning_applied=False,
                )
                priority["learning_state"] = "observe_only"
                priority["effect_learning_recorded"] = False
                priority["behavior_observation"] = observation
                return priority
            # A learning experiment is only credited when the learned strategy
            # produces a measurable behavioral difference against a stored baseline.
            meta = priority.get("meta", {})
            experiment = loop.observe_behavior(
                goal, answer, strategy=str(meta.get("strategy") or getattr(trace, "intent", "general") or "default"),
                domain="dialogue", episode_id=str(getattr(trace, "cycle_id", "") or ""),
                learning_applied=True,
            )
            priority["behavior_experiment"] = experiment
            if experiment.get("mode") != "compared" or not experiment.get("changed"):
                priority["effect_learning_recorded"] = False
                priority["learning_state"] = "experiment_observed"
                return priority
            strategy = str(meta.get("strategy") or getattr(trace, "intent", "general") or "default")
            transfer_source = loop.find_transfer_source(goal, "dialogue", min_similarity=.25)
            if transfer_source is None:
                priority["learning_state"] = "awaiting_transfer_case"
                priority["transfer"] = {"passed": False, "reason": "no_similar_prior_case"}
                priority["effect_learning_recorded"] = False
                return priority
            transfer = loop.evaluate_transfer(
                transfer_source.get("goal",""), goal, answer,
                "رفتار آموخته‌شده باید روی مسئله مشابه نیز با موفقیت اجرا شود",
                {"verified": getattr(trace, "verification_status", "") == "PASS",
                 "score": confidence},
                strategy=strategy, domain="dialogue",
                episode_id=str(getattr(trace, "cycle_id", "") or ""), attempt=1)
            priority["transfer"] = transfer
            if not transfer.get("passed"):
                priority["learning_state"] = "transfer_failed"
                priority["effect_learning_recorded"] = False
                return priority
            verification = {
                "verified": getattr(trace, "verification_status", "") == "PASS",
                "score": confidence,
                "effect_observed": getattr(trace, "verification_status", "") == "PASS" and confidence >= .75,
            }
            gate = loop.learning_result(experiment.get("comparison", {}), verification, transfer)
            priority["learning_gate"] = gate
            if not gate.get("qualified"):
                priority["learning_state"] = "evidence_chain_incomplete"
                priority["effect_learning_recorded"] = False
                return priority
            expected = "پاسخ در مسیر یادگیری انتخاب‌شده با راستی‌آزمایی و حفظ زمینه اجرا شود"
            result = str(answer)
            effect = loop.evaluate(goal, "canonical_turn", result, expected, verification,
                                   strategy=strategy, domain="dialogue",
                                   episode_id=str(getattr(trace, "cycle_id", "") or ""), attempt=1,
                                   allow_credit=bool(gate.get("xp_eligible")))
            self.runtime.events.emit("learning_effect_evaluated", {
                "goal": goal, "action": action, "strategy": strategy,
                "effect": effect, "canonical": True,
            })
            return {"priority": priority, "effect": effect}
        except Exception as exc:
            try:
                self.runtime.events.emit("learning_effect_error", {"error": str(exc), "canonical": True})
            except Exception:
                pass
            return {}

    def guidance(self, goal: str, intent: str = "general", domain: str = "general") -> dict:
        """Return reusable learned guidance for any cognitive capability, not only dialogue."""
        learning = getattr(self.runtime, "learning", None)
        if learning is None:
            return {}
        try:
            result = learning.adapt(str(goal), str(intent), str(domain)) or {}
            result["failure_signal"] = bool(learning.failure_patterns(6))
            return result
        except Exception:
            return {}

    def record_outcome(self, goal, action, result, expected, verification, strategy="default", domain="general"):
        """Feed a verified outcome back into the shared learning brain."""
        core = getattr(self.runtime, "outcome_learning", None)
        if core is None:
            return {"verified": False, "learned": False, "reason": "outcome_learning_unavailable"}
        return core.record_outcome(goal, action, result, expected, verification,
                                   strategy=strategy, domain=domain)

    def unified_output(self) -> dict:
        """Return the current answer plus the live state of every integrated stage."""
        trace = self.last_trace
        runtime = self.runtime
        return {
            "version": self.VERSION,
            "answer": self.last_answer,
            "trace": trace.__dict__.copy() if trace is not None else {},
            "architecture": self.architecture_contract(),
            "components": self.inspect(),
            "memory": runtime.memory.stats() if getattr(runtime, "memory", None) else {},
            "knowledge": runtime.knowledge.stats() if getattr(runtime, "knowledge", None) else {},
            "learning": self.learning_status(),
            "learning_gate": runtime.learning_status() if hasattr(runtime, "learning_status") else {},
            "autonomy": self.autonomy_status(),
            "improvement": self.improvement_status(),
            "conversation": runtime.conversation_snapshot() if hasattr(runtime, "conversation_snapshot") else {},
        }

    def inspect(self) -> dict:
        """Return a compact live map of the unified dependency graph."""
        runtime = self.runtime
        pipe = self.pipeline
        return {
            "version": self.VERSION,
            "entrypoint": "CognitiveSystem.dispatch",
            "pipeline": "CognitivePipeline.run",
            "memory": type(getattr(runtime, "memory", None)).__name__,
            "knowledge": type(getattr(runtime, "knowledge", None)).__name__,
            "learning": type(getattr(runtime, "learning", None)).__name__,
            "reasoning": type(getattr(pipe, "reasoning_planning", None)).__name__,
            "semantic_verification": type(getattr(pipe, "semantic_verifier", None)).__name__,
            "chain_reasoner": bool(getattr(self.dialogue, "chain_reasoner", None)),
            "grounded_synthesis": bool(getattr(self.dialogue, "grounded_synthesizer", None)),
            "self_correction": bool(getattr(self.pipeline, "self_correction", None) or getattr(self.dialogue, "self_correction", None)),
            "autonomy": bool(
                getattr(runtime, "autonomous_supervisor", None)
                or getattr(runtime, "autonomy", None)
            ),
            "self_improvement": type(getattr(runtime, "improvement", None)).__name__,
            "self_directed_learning": type(getattr(runtime, "self_directed_learning", None)).__name__,
            "trusted_knowledge": type(getattr(runtime, "trusted_knowledge", None)).__name__,
            "learning_gate": type(getattr(runtime, "learning_gate", None)).__name__,
        }

    def learning_status(self) -> dict:
        learning = getattr(self.runtime, "learning", None)
        if learning is None:
            return {"available": False}
        try:
            return {"available": True, **learning.stats()}
        except Exception as exc:
            return {"available": True, "error": str(exc)}

    def improvement_status(self) -> dict:
        improvement = getattr(self.runtime, "improvement", None)
        if improvement is None:
            return {"available": False}
        try:
            return {"available": True, **improvement.status()}
        except Exception as exc:
            return {"available": True, "error": str(exc)}

    def autonomy_status(self) -> dict:
        supervisor = getattr(self.runtime, "autonomous_supervisor", None)
        controller = getattr(self.runtime, "autonomy", None)
        target = supervisor or controller
        if target is None:
            return {"available": False}
        for method in ("snapshot", "status"):
            fn = getattr(target, method, None)
            if callable(fn):
                try:
                    value = fn()
                    return {"available": True, "state": value}
                except Exception:
                    pass
        return {"available": True, "type": type(target).__name__}

    def bind_legacy_adapters(self) -> None:
        """Bind legacy names to this composition root; they remain compatibility adapters."""
        runtime = self.runtime
        for name in ("brain", "cognition_engine", "kernel", "cognitive_core", "orchestrator"):
            component = getattr(runtime, name, None)
            if component is not None:
                try:
                    component._canonical_system = self
                except Exception:
                    pass

    def kernel_cycle_compat(self, text: str):
        """Compatibility view of a kernel cycle without creating a second decision path."""
        from core.kernel import CycleResult
        answer = self.pipeline.run(str(text))
        t = getattr(self.dialogue, "last_trace", None)
        return CycleResult(
            goal=str(text),
            intent=getattr(t, "intent", "general"),
            confidence=float(getattr(t, "confidence", 0.0)),
            reasoning={"canonical": True, "trace": getattr(t, "__dict__", {})},
            predictions=[],
            anomaly={},
            elapsed_ms=float(getattr(t, "elapsed_ms", 0.0)),
            understanding={"answer": answer, "canonical": True},
            causal={},
            strategy={"source": "CognitiveSystem"},
        )

    def advanced_core_compat(self, text: str):
        """Compatibility view of AdvancedCognitiveCore backed by the canonical turn."""
        self.pipeline.run(str(text))
        state = getattr(self.dialogue, "state", None)
        return state if state is not None else {"text": str(text)}

    def close(self) -> None:
        self.last_answer = ""
        self.last_trace = None
        self.last_output = {}

    def architecture_contract(self) -> dict:
        """Expose the canonical order used by the integrated turn."""
        return {
            "perception": "dialogue.parse",
            "context": "conversation_state + context_tracker",
            "memory": "MemoryIntelligence + UserModel + episodic/semantic memory",
            "knowledge": "KnowledgeGraph",
            "reasoning": "ChainReasoner + ReasoningPlanningEngine",
            "planning": "AnswerPlanner / planning subsystem",
            "generation": "local deterministic response synthesis",
            "verification": "AnswerVerifier + SemanticVerifier + repair",
            "commit": "ConversationState + memory outcome",
            "learning": "LearningEngine + OutcomeBackedLearning",
            "autonomy": "AutonomousSupervisor / AutonomousController",
            "improvement": "SelfImprovementLoop with sandbox/rollback",
            "entrypoint": "CognitiveSystem.turn",
            "legacy_components": {
                "Brain": "compatibility/input facade",
                "CognitiveEngine": "compatibility facade",
                "AdvancedCognitiveCore": "compatibility facade",
                "CognitiveKernel": "compatibility facade",
                "Orchestrator": "compatibility facade",
            },
            "decision_owner": "CognitiveSystem",
            "parallel_decision_paths": False,
        }
