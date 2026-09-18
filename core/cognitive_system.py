from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.cognitive_pipeline import CognitivePipeline


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
        answer = self.pipeline.run(text)
        self.last_answer = answer
        self.last_trace = getattr(self.dialogue, "last_trace", None)
        self.last_output = self.unified_output()
        return answer

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
            "self_correction": bool(getattr(self.dialogue, "self_correction", None)),
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

    def close(self) -> None:
        self.last_answer = ""
        self.last_trace = None
        self.last_output = {}
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
        }
