"""Single offline natural-language execution path for IRAN."""
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
    """One user-turn boundary joining perception, cognition, dialogue and learning."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.turns = 0
        self.last_result = None

    def handle(self, text):
        started = perf_counter()
        clean = str(text or "").strip()
        if not clean:
            return "لطفاً یک پیام وارد کن."

        self.turns += 1
        runtime = self.runtime
        runtime.events.begin_turn()

        extracted = runtime.user_model.record(clean) if hasattr(runtime, "user_model") else []
        if extracted:
            runtime.events.emit("user_model_update", {
                "extracted": extracted,
                "count": len(extracted),
                "source": "unified_pipeline",
            })

        try:
            auto = runtime.orchestrator._auto_tool(clean)
        except Exception:
            auto = None
        if auto is not None:
            runtime.memory.add("tool_result", auto, .78)
            runtime.events.emit("response_generated", {
                "goal": clean,
                "route": "tool",
                "mode": "TOOL",
                "verified": True,
                "score": 1.0,
            })
            return auto

        state = runtime.cognitive_core.begin(clean)
        runtime.events.emit("language_analysis", {
            "intent": state.intent,
            "confidence": state.intent_confidence,
            "entities": state.entities,
            "constraints": state.references,
            "ambiguity": len(state.unresolved),
            "canonical": True,
        })
        runtime.events.emit("cognitive_cycle", {
            "intent": state.intent,
            "confidence": state.confidence,
            "decision": state.executive,
            "unified": True,
        })
        runtime.events.emit("plan_created", {
            "goal": state.goal,
            "version": 1,
            "steps": state.plan,
            "canonical": True,
        })

        answer = runtime.dialogue.handle(clean)
        if self._is_greeting(clean):
            answer = "سلام 👋 من ایران هستم؛ خوشحالم می‌بینمت. امروز درباره چی حرف بزنیم؟"
        elif self._needs_clarification(clean, runtime):
            answer = "منظورت کدام موضوع یا مرجع است؟ اگر موضوع قبلی را می‌خواهی ادامه بدهم، نام موضوع را بگو."

        # Explicit personal facts should be reflected immediately and deterministically.
        if extracted and not self._is_question(clean):
            facts = []
            for fact in extracted:
                predicate = fact.get("predicate")
                obj = str(fact.get("object", "")).strip()
                if predicate == "role" and obj == "creator":
                    facts.append("متوجه شدم؛ تو سازنده پروژه IRAN هستی.")
                elif predicate == "likes" and obj:
                    facts.append(f"متوجه شدم؛ تو {obj} را دوست داری.")
                elif predicate == "dislikes" and obj:
                    facts.append(f"متوجه شدم؛ تو {obj} را دوست نداری.")
                elif predicate == "name" and obj:
                    facts.append(f"متوجه شدم؛ اسمت {obj} است.")
            if facts:
                answer = " ".join(facts)

        verification = runtime.cognitive_core.verify(state, answer)
        executive = runtime.cognitive_core.complete_executive(answer)
        runtime.cognitive_core.learn(answer, verification.get("score", 0.0))

        elapsed = round((perf_counter() - started) * 1000, 2)
        try:
            runtime.orchestrator.metrics.record("response", perf_counter() - started)
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
            score = verification.get("score", 0.0)
            runtime.events.emit("evaluation_completed", {
                "score": score,
                "mode": mode,
                "canonical": True,
            })
            runtime.events.emit("reflection", {
                "score": score,
                "executive_status": executive.status,
                "canonical": True,
            })
            runtime.events.emit("learning_update", {
                "score": score,
                "strategy": "conversation",
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
                "score": score,
                "elapsed_ms": elapsed,
            })
        except Exception:
            pass
        return result.answer

    @staticmethod
    def _is_greeting(text):
        normalized = text.strip().lower()
        return normalized in {"سلام", "سلام!", "سلام؟", "hello", "hi", "درود"}

    @staticmethod
    def _needs_clarification(text, runtime):
        markers = ("همون قبلی", "همان قبلی", "ادامه بده", "ادامه‌ش بده", "ادامه اش بده")
        if not any(marker in text for marker in markers):
            return False
        dialogue = getattr(runtime, "dialogue", None)
        state = getattr(dialogue, "state", None)
        current = str(getattr(state, "current_topic", "") or "")
        goal = str(getattr(state, "active_goal", "") or "")
        if any(marker in current for marker in markers) or any(marker in goal for marker in markers):
            return True
        return not bool(current or goal)

    @staticmethod
    def _is_question(text):
        return "؟" in text or "?" in text or text.strip().startswith(("چرا", "چی", "چه", "کجا", "کی", "چطور", "چگونه", "آیا"))

    def snapshot(self):
        if self.last_result is None:
            return {"turns": self.turns, "last": None}
        return {"turns": self.turns, "last": asdict(self.last_result)}
