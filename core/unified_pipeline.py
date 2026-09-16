"""Single natural-language execution path for the IRAN runtime.

The pipeline is deliberately small: perception/cognition happens once,
the canonical dialogue engine produces the answer, and the same cognitive
state is then verified and closed through the symbolic executive cycle.
No model, network service, or second response generator is involved.
"""
from dataclasses import dataclass, asdict
from time import perf_counter


@dataclass
class PipelineResult:
    text: str
    answer: str
    verification: dict
    executive: dict
    elapsed_ms: float


class UnifiedCognitivePipeline:
    """Canonical user-turn boundary joining cognition, dialogue and learning."""

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

        # Explicit facts are learned before cognition; questions never invent facts.
        extracted = runtime.user_model.record(clean) if hasattr(runtime, "user_model") else []
        if extracted:
            runtime.events.emit("user_model_update", {
                "extracted": extracted, "count": len(extracted), "source": "unified_pipeline"
            })

        # Explicit local tools keep their permission-gated contract.
        try:
            auto = runtime.orchestrator._auto_tool(clean)
        except Exception:
            auto = None
        if auto is not None:
            runtime.memory.add("tool_result", auto, .78)
            runtime.events.emit("response_generated", {
                "goal": clean, "route": "tool", "mode": "TOOL",
                "verified": True, "score": 1.0,
            })
            return auto

        cognitive = runtime.cognitive_core

        # One perception/cognition pass. The core owns working memory,
        # metacognition, causal/analogical reasoning and the executive cycle.
        state = cognitive.begin(clean)

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

        # Canonical dialogue is the only natural-language answer producer.
        answer = runtime.dialogue.handle(clean)
        if extracted and "؟" not in clean and "?" not in clean:
            facts = []
            for fact in extracted:
                predicate, obj = fact.get("predicate"), fact.get("object")
                if predicate == "role" and obj == "creator":
                    facts.append("نقش شما در پروژه IRAN به‌عنوان سازنده ثبت شد.")
                elif predicate == "likes":
                    facts.append(f"ترجیح شما ثبت شد: «{obj}» را دوست دارید.")
                elif predicate == "dislikes":
                    facts.append(f"ترجیح شما ثبت شد: «{obj}» را دوست ندارید.")
                elif predicate == "name":
                    facts.append(f"نام شما «{obj}» ثبت شد.")
            if facts:
                answer = " ".join(facts)

        # Verify the actual answer against the same state that planned it.
        verification = cognitive.verify(state, answer)
        executive = cognitive.complete_executive(answer)
        cognitive.learn(answer, verification.get("score", 0.0))

        elapsed = round((perf_counter() - started) * 1000, 2)
        try:
            runtime.orchestrator.metrics.record("response", (perf_counter() - started))
        except Exception:
            pass
        result = PipelineResult(
            text=clean,
            answer=str(answer),
            verification=verification,
            executive=executive.__dict__.copy(),
            elapsed_ms=elapsed,
        )
        self.last_result = result

        try:
            mode = runtime.answer_generator.mode(result.answer) if hasattr(runtime, "answer_generator") else "DIRECT"
            if state.evidence and result.answer.strip() and mode == "UNKNOWN":
                mode = "DIRECT_FACT"
            runtime.events.emit("evaluation_completed", {
                "score": verification.get("score", 0.0), "mode": mode, "canonical": True,
            })
            runtime.events.emit("reflection", {
                "score": verification.get("score", 0.0),
                "executive_status": executive.status,
                "canonical": True,
            })
            runtime.events.emit("learning_update", {
                "score": verification.get("score", 0.0), "strategy": "conversation",
                "canonical": True,
            })
            runtime.events.emit("unified_pipeline", {
                "turn": self.turns,
                "verification": verification,
                "executive": result.executive,
                "elapsed_ms": elapsed,
            })
            runtime.events.emit("response_generated", {
                "goal": clean,
                "route": "unified_pipeline",
                "mode": mode,
                "verified": bool(verification.get("passed")),
                "score": verification.get("score", 0.0),
                "elapsed_ms": elapsed,
            })
        except Exception:
            pass
        return result.answer

    def snapshot(self):
        if self.last_result is None:
            return {"turns": self.turns, "last": None}
        return {"turns": self.turns, "last": asdict(self.last_result)}
