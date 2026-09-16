"""Single cognitive turn boundary for IRAN.

Every natural-language turn follows perception -> memory -> reasoning -> planning
-> realization -> verification -> learning. No question/answer response cache is
used as a conversational shortcut.
"""
from dataclasses import dataclass, asdict
from time import perf_counter
from .answer_generator import AnswerGenerator
from .response_engine import LocalResponseEngine


@dataclass
class PipelineResult:
    text: str
    answer: str
    verification: dict
    executive: dict
    elapsed_ms: float


class UnifiedCognitivePipeline:
    """One deterministic symbolic cognitive path for every natural-language turn."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.turns = 0
        self.last_result = None

    def handle(self, text):
        started = perf_counter()
        clean = str(text or "").strip()
        if not clean:
            return "چیزی برای پردازش دریافت نکردم."
        self.turns += 1
        runtime = self.runtime
        runtime.events.begin_turn()

        # Observation only: explicit user facts become evidence, never an answer.
        extracted = runtime.user_model.record(clean) if hasattr(runtime, "user_model") else []
        if extracted:
            runtime.events.emit("user_model_update", {"extracted": extracted, "count": len(extracted), "source": "cognition"})

        # Tool execution is reserved for explicit command semantics; normal dialogue
        # never exits through a question-specific response route.
        try:
            auto = runtime.orchestrator._auto_tool(clean)
        except Exception:
            auto = None
        if auto is not None:
            runtime.memory.add("tool_result", auto, .78)
            runtime.events.emit("tool_observation", {"goal": clean, "result": str(auto)[:500], "cognitive": True})

        state = runtime.cognitive_core.begin(clean)
        runtime.events.emit("language_analysis", {
            "intent": state.intent, "confidence": state.intent_confidence,
            "entities": state.entities, "constraints": state.references,
            "ambiguity": len(state.unresolved), "canonical": True,
        })
        runtime.events.emit("cognitive_cycle", {
            "intent": state.intent, "confidence": state.confidence,
            "decision": state.executive, "unified": True,
        })
        runtime.events.emit("plan_created", {
            "goal": state.goal, "version": 1, "steps": state.plan, "canonical": True,
        })

        # The answer is synthesized from the current cognitive state and local
        # evidence. The engine is not given a question->answer lookup table.
        engine = getattr(runtime.provider, "response_engine", None) or LocalResponseEngine()
        generator = getattr(runtime, "answer_generator", None)
        if generator is None:
            generator = AnswerGenerator(engine, getattr(runtime, "knowledge", None), runtime=runtime)
        generator.engine = engine
        cycle = state.__dict__.copy() if hasattr(state, "__dict__") else dict(state)
        cycle["user_model"] = runtime.user_model.profile(clean, 12) if hasattr(runtime, "user_model") else {}
        cycle["current_observations"] = extracted
        cycle["memory_context"] = runtime.memory.working_context(clean, 12)
        history = [item for item in runtime.memory.recent(runtime.config["memory"].get("max_history", 16))
                   if isinstance(item, (tuple, list)) and len(item) >= 3 and item[0] in {"user", "fact", "goal", "lesson"}]
        parsed = runtime.language_intelligence.analyze(clean, getattr(runtime.brain, "frame", {})) if hasattr(runtime, "language_intelligence") else runtime.brain.language.parse(clean)
        answer_result = generator.generate(clean, parsed, cycle, history, getattr(runtime.provider, "frame", {}))
        answer = str(answer_result.text)

        verification = runtime.cognitive_core.verify(state, answer)
        executive = runtime.cognitive_core.complete_executive(answer)
        runtime.cognitive_core.learn(answer, verification.get("score", 0.0))
        elapsed = round((perf_counter() - started) * 1000, 2)
        result = PipelineResult(clean, answer, verification, executive.__dict__.copy(), elapsed)
        self.last_result = result

        score = verification.get("score", 0.0)
        runtime.events.emit("evaluation_completed", {"score": score, "mode": answer_result.mode, "canonical": True})
        runtime.events.emit("reflection", {"score": score, "executive_status": executive.status, "canonical": True})
        runtime.events.emit("learning_update", {"score": score, "strategy": "cognitive_turn", "canonical": True})
        runtime.events.emit("unified_pipeline", {"turn": self.turns, "verification": verification, "executive": result.executive, "elapsed_ms": elapsed})
        runtime.events.emit("response_generated", {
            "goal": clean, "route": "unified_cognitive_response", "mode": answer_result.mode,
            "verified": bool(verification.get("passed")), "score": score, "elapsed_ms": elapsed,
        })
        return answer

    def snapshot(self):
        if self.last_result is None:
            return {"turns": self.turns, "last": None}
        return {"turns": self.turns, "last": asdict(self.last_result)}
