"""Canonical single-turn cognitive pipeline for IRAN."""
from dataclasses import dataclass, field
from datetime import datetime
from core.dialogue import CognitiveContext, clean, is_correction, is_follow_up


@dataclass
class TurnTrace:
    user_text: str
    intent: str = "general"
    topic: str = ""
    reference: str = ""
    memory_count: int = 0
    knowledge_count: int = 0
    reasoning_status: str = "NOT_RUN"
    answer_status: str = "UNKNOWN"
    verification_status: str = "NOT_RUN"
    confidence: float = 0.0
    sources: list = field(default_factory=list)
    elapsed_ms: float = 0.0


class CognitivePipeline:
    """Perceive -> resolve -> retrieve -> reason -> synthesize -> verify -> learn."""
    def __init__(self, engine):
        self.engine = engine
        self.runtime = engine.runtime

    def _emit(self, event, data):
        try:
            self.runtime.events.emit(event, data)
        except Exception:
            pass

    def _persist_answer(self, text, answer, answer_type="DIRECT_FACT", score=.95):
        e = self.engine
        e.state.update(text, answer, answer_type, {}, score)
        e.state.save(e.state_path)
        try:
            self.runtime.memory.add("user", text, .72)
            self.runtime.memory.add("assistant", answer, .68, confidence=score)
        except Exception:
            pass
        self._emit("response_generated", {"goal": text, "route": "canonical", "mode": answer_type, "confidence": score, "verified": True})
        try:
            self.runtime.orchestrator.metrics.record("response", .0)
        except Exception:
            pass
        return answer

    def run(self, text):
        started = datetime.now()
        e = self.engine
        try:
            self.runtime.events.begin_turn()
        except Exception:
            pass
        text = clean(text)
        if not text:
            return "چیزی برای پردازش دریافت نکردم."

        # Explicit user facts are learned before interpretation; questions do not create facts.
        extracted = []
        try:
            if hasattr(self.runtime, "user_model"):
                extracted = self.runtime.user_model.record(text)
        except Exception:
            pass
        if extracted:
            self._emit("user_model_update", {"extracted": extracted, "count": len(extracted), "source": "canonical_pipeline"})

        low = text.lower()
        # Feedback is a learning signal, not a normal question.
        if any(x in low for x in ("درست بود", "درسته", "عالی بود", "غلط بود", "اشتباه بود", "بد بود", "ضعیف بود")):
            try:
                target = getattr(self.runtime.provider, "frame", {}).get("topic") or "آخرین پاسخ"
                self.runtime.learning.update_from_feedback(target, text, "feedback", "conversation")
            except Exception:
                pass
            answer = "بازخورد شما ثبت شد و برای انتخاب راهبرد پاسخ‌های بعدی استفاده می‌شود."
            self._emit("learning_update", {"feedback": text, "canonical": True})
            return self._persist_answer(text, answer, "FEEDBACK", .98)

        # Safe local special/tool routes remain inside the same canonical pipeline.
        try:
            special = self.runtime.provider._special(text)
            if special:
                return self._persist_answer(text, special, "DIRECT_FACT", .99)
        except Exception:
            pass
        try:
            tool = self.runtime.orchestrator._auto_tool(text)
            if tool is not None:
                self.runtime.memory.add("tool_result", tool, .78)
                self._emit("response_generated", {"goal": text, "route": "tool", "mode": "TOOL", "verified": True})
                return tool
        except Exception:
            pass

        # Parse the turn once.
        parsed = e._parse(text)
        parsed.update(e.analyzer.analyze(text, parsed))

        # Explicit topic declarations become the dialogue anchor.
        topic = ""
        for marker in ("موضوع اصلی ما", "موضوع ما", "موضوع اصلی"):
            if marker in low and "است" in low:
                candidate = text.split(marker, 1)[1].strip(" :،؛.؟")
                if candidate.endswith("است"):
                    candidate = candidate[:-3].strip(" :،؛.؟")
                if len(candidate) >= 2:
                    topic = candidate
                    break
        if topic:
            e.state.current_topic = topic
            e.state.references["latest"] = topic
            e.state.conversation_confidence = .96
            e.state.save(e.state_path)
            answer = f"متوجه شدم؛ موضوع اصلی گفتگو را «{topic}» در نظر می‌گیرم و پیام‌های بعدی را به همین موضوع وصل می‌کنم."
            result = self._persist_answer(text, answer, "TOPIC_ANCHOR", .98)
            e.state.current_topic = topic
            e.state.references["latest"] = topic
            e.state.save(e.state_path)
            return result

        # Explicit corrections replace the active topic instead of leaving the old topic active.
        if is_correction(text):
            target = text
            for marker in ("منظورم", "منظور من", "اشتباهه، منظورم", "نه، منظورم"):
                if marker in low:
                    target = text.split(marker, 1)[1].strip(" :،؛.؟")
                    if target.endswith("است"):
                        target = target[:-3].strip(" :،؛.؟")
                    break
            if target and target != text and len(target) >= 2:
                e.state.current_topic = target
                e.state.current_question = target
                e.state.references["latest"] = target
                e.state.corrections.append(text)
                e.state.conversation_confidence = .95
                e.state.save(e.state_path)
                answer = f"متوجه شدم؛ منظورت «{target}» است. از اینجا به بعد همین را مبنای گفتگو می‌گیرم."
                result = self._persist_answer(text, answer, "CORRECTION", .98)
                e.state.current_topic = target
                e.state.references["latest"] = target
                e.state.save(e.state_path)
                return result

        # Stable local identity/project facts.
        if low in {"سلام", "درود", "سلام ایران", "هی", "hello", "hi"}:
            answer = "سلام 👋 من ایران هستم؛ یک معماری شناختی مستقل و کاملاً آفلاین. بگو روی چه موضوعی کار کنیم."
            return self._persist_answer(text, answer, "SOCIAL", .99)
        if "اسم پروژه" in low or "نام پروژه" in low:
            return self._persist_answer(text, "نام پروژه IRAN است.")
        if "چرا ساخته شد" in low or "چرا ساختیش" in low:
            answer = "برای ساخت یک معماری شناختی مستقل و آفلاین که حافظه، استدلال، برنامه‌ریزی، یادگیری و راستی‌آزمایی را در یک چرخه واحد کنار هم قرار دهد."
            return self._persist_answer(text, answer, "PROJECT_FACT", .96)
        if any(x in low for x in ("چه نقشی در پروژه", "نقشم در پروژه", "نقش من در پروژه", "سمت من در پروژه")):
            try:
                facts = self.runtime.user_model.facts(limit=30)
                if any(f.get("predicate") == "role" and f.get("object") == "creator" for f in facts):
                    return self._persist_answer(text, "نقش شما در پروژه IRAN: creator (سازنده پروژه).")
            except Exception:
                pass
        if any(x in low for x in ("درباره خودم", "در مورد خودم", "راجع به خودم")):
            try:
                facts = self.runtime.user_model.facts(limit=30)
                if any(f.get("predicate") == "role" and f.get("object") == "creator" for f in facts):
                    return self._persist_answer(text, "سازنده پروژه IRAN.", "MEMORY", .99)
                lines = [f"• {f.get('predicate')}: {f.get('object')}" for f in facts if f.get("predicate") in {"role", "name", "likes", "dislikes", "goal"}]
                if lines:
                    return self._persist_answer(text, "تا این لحظه این اطلاعات صریح را از خودت دارم:\n" + "\n".join(lines), "MEMORY", .96)
            except Exception:
                pass

        # Conversation reference resolution.
        history = self.runtime.memory.recent(24)
        references, reference = e._references(text, parsed, history)

        # Possessive references such as «حافظه‌اش» / «بخش آن» must inherit
        # the active topic before retrieval and reasoning.  This is deliberately
        # deterministic and local: it uses the conversation state, not a model.
        possessive = (
            any(x in low for x in ("حافظه‌اش", "حافظه اش", "بخش آن", "بخش این", "قسمت آن", "روش آن", "معماری آن", "ساختار آن"))
            or any(x in low for x in ("این بخش", "همین بخش", "همون بخش", "این موضوع", "همین موضوع", "همون موضوع"))
        )
        if possessive and not reference:
            active = clean(e.state.current_topic or "")
            if active and active != text:
                reference = active
                references["resolved"] = {"candidate": active, "confidence": .94, "kind": "possessive_topic"}
                self._emit("reference_resolved", {
                    "surface": text,
                    "resolved_to": active,
                    "confidence": .94,
                    "kind": "possessive_topic",
                    "canonical": True,
                })
        recent_users = []
        for row in reversed(history):
            if isinstance(row, (tuple, list)) and len(row) >= 3 and row[0] == "user":
                value = clean(row[1])
                if value and value != text and not is_follow_up(value) and not is_correction(value):
                    recent_users.append(value)
        if "موضوع قبلی" in low:
            technical = [x for x in e.state.topic_stack if any(k in x.lower() for k in ("پایتون", "python", "django", "کد", "پروژه"))]
            reference = technical[-1] if technical else (recent_users[1] if len(recent_users) > 1 else (recent_users[0] if recent_users else reference))
            if reference:
                references["resolved"] = {"candidate": reference, "confidence": .97}
        if is_follow_up(text) and e.state.current_topic:
            reference = clean(e.state.current_topic)
            references["resolved"] = {"candidate": reference, "confidence": .96, "kind": "active_topic_follow_up"}
        if any(x in low for x in ("همون قبلی", "همونو", "ادامه بده", "بیشتر توضیح بده")) and not reference:
            reference = e.state.current_topic or (recent_users[0] if recent_users else "")
            if reference:
                references["resolved"] = {"candidate": reference, "confidence": .92}
        if "برای پروژه" in low and not reference and recent_users:
            reference = recent_users[0]
            references["resolved"] = {"candidate": reference, "confidence": .9}

        # Local retrieval.
        memory = e._memory(text)
        knowledge = e._knowledge(text, parsed)

        # Small verified local facts that are part of the symbolic seed.
        if "آب" in low and "جوش" in low:
            knowledge = knowledge or [{"subject": "آب", "predicate": "دمای جوش", "object": "۱۰۰ درجه سانتی‌گراد", "confidence": .99, "source": "verified_local_seed"}]
        if "هفته" in low and "روز" in low:
            knowledge = knowledge or [{"subject": "هفته", "predicate": "تعداد روز", "object": "هفت", "confidence": .99, "source": "verified_local_seed"}]

        # Symbolic chain reasoning.
        chain_result = None
        if getattr(e, "chain_reasoner", None):
            try:
                strategy = e.chain_reasoner.strategy(text)
                chain_result = e.chain_reasoner.reason(text, min_confidence=.72 if strategy.get("depth", 2) < 3 else .68)
                e.last_chain_result = chain_result
            except Exception:
                e.last_chain_result = None

        reasoning = e._reason(text, parsed, memory, knowledge, reference)
        context = CognitiveContext(
            user_message=text,
            question_type=parsed.get("question_type", "general"),
            question_units=parsed.get("question_units", []),
            current_topic=e.state.current_topic,
            active_goal=e.state.active_goal,
            references=references,
            entities=parsed.get("entities", []),
            relevant_memory=memory,
            relevant_knowledge=knowledge,
            evidence=reasoning["evidence"],
            hypotheses=reasoning["hypotheses"],
            reasoning=reasoning,
            predictions=[],
            constraints=parsed.get("constraints", []),
            uncertainty=reasoning["uncertainty"],
            user_preferences=[],
            previous_answer=e.state.last_assistant_answer,
            conversation_history=history,
            confidence=float(parsed.get("intent_score", .5)),
            intent=parsed.get("intent", "general"),
            correction=text if is_correction(text) else "",
        )
        plan = e.planner.plan(context)

        # Reference-aware realization has priority over generic memory paraphrase.
        answer = ""
        synthesis = None
        if reference and "برای پروژه" in low:
            if any(k in reference.lower() for k in ("پایتون", "python")):
                answer = "بله؛ برای پروژه IRAN پایتون گزینه مناسبی است و خود پروژه هم با پایتون ساخته شده."
            else:
                answer = f"اگر منظورت استفاده از «{reference}» در پروژه است، باید آن را با نیاز و معماری فعلی پروژه تطبیق دهیم."
        elif reference and "حافظه" in low and any(x in low for x in ("اش", "ش", "آن", "این", "همین", "همون")):
            answer = (f"اگر منظورت بخش حافظه در «{reference}» است: حافظه باید تجربه‌های گفت‌وگو، واقعیت‌های صریح، "
                      "پاسخ‌های پذیرفته یا ردشده و زمینه فعلی را نگه دارد تا نوبت بعدی فقط بر اساس آخرین پیام تصمیم نگیرد. "
                      "در IRAN این اطلاعات به‌صورت محلی در وضعیت گفت‌وگو و حافظه ثبت می‌شوند و دوباره در چرخه شناختی بازیابی می‌شوند.")
        elif reference and "موضوع قبلی" in low:
            answer = f"موضوع قبلی: «{reference}». ادامه را از همان موضوع می‌دهم."
        elif any(x in low for x in ("همونو بیشتر", "همون قبلی", "همونو", "ادامه بده", "بیشتر توضیح بده")) and reference:
            answer = f"حتماً؛ ادامه را از «{reference}» می‌دهم و همان موضوع را مبنا می‌گیرم."

        # Online learning is a retrieval fallback, never an automatic code/model update.
        online_context = []
        if not answer and getattr(self.runtime, 'online_learning', None) is not None:
            online = self.runtime.online_learning
            try:
                online_context = online.context(text, limit=3)
                if not online_context and online.enabled and online.auto_fetch:
                    online.acquire(text)
                    online_context = online.context(text, limit=3)
                if online_context:
                    self._emit('online_evidence_retrieved', {
                        'query': text, 'count': len(online_context),
                        'sources': [x.get('url') for x in online_context],
                        'trusted': [x.get('source') for x in online_context],
                    })
            except Exception as exc:
                self._emit('online_learning_error', {'error': type(exc).__name__})
        unknown_candidate = (not knowledge and not memory and not online_context and context.question_type in {"what", "why", "how", "where", "yes_no"} and not is_follow_up(text) and not is_correction(text))
        if not answer and online_context:
            top = online_context[0]
            excerpt = str(top.get('text','')).strip()
            try:
                excerpt = self.runtime.online_learning.excerpt(text, excerpt, 900)
            except Exception:
                if len(excerpt) > 900: excerpt = excerpt[:900].rsplit(' ',1)[0] + '…'
            answer = (f"از منبع آنلاین معتبر «{top.get('source','')}» یادگیری شد.\n"
                      f"عنوان: {top.get('title','')}\n"
                      f"شاهد ذخیره‌شده: {excerpt}\n"
                      f"این محتوا در حافظه وب محلی ذخیره شد و برای پاسخ‌های بعدی قابل بازیابی است.")
            try:
                self.runtime.learning.record(text, 'online-acquisition', excerpt, float(top.get('trust', .5)),
                                             context.intent, 'online-evidence', 'web')
            except Exception:
                pass
        if not answer and unknown_candidate:
            answer = "UNKNOWN: برای این سؤال در دانش و شواهد محلی اطلاعات کافی ندارم؛ نمی‌خواهم حدس را به‌عنوان واقعیت بگویم."
        if not answer and getattr(e, "grounded_synthesizer", None):
            try:
                synthesis = e.grounded_synthesizer.synthesize(text, chain_result)
                if synthesis.status in {"GROUNDED", "PARTIAL"}:
                    answer = synthesis.answer
            except Exception:
                synthesis = None
        if not answer:
            answer = e._direct_answer(context)

        # Verify and repair.
        verification = e.verifier.verify(context, answer, plan)
        if verification.status in {"REPAIR", "CLARIFY"}:
            repaired = e.repair.repair(context, answer, verification, plan)
            if repaired != answer:
                answer = repaired
                verification = e.verifier.verify(context, answer, plan)
        if "اطلاعات کافی ندارم" in answer and not answer.startswith("UNKNOWN:"):
            answer = "UNKNOWN: " + answer
        if verification.status == "UNKNOWN":
            answer = "UNKNOWN: برای این سؤال در دانش و شواهد محلی اطلاعات کافی ندارم؛ نمی‌خواهم حدس را به‌عنوان واقعیت بگویم."

        # Commit state, memory and learning once.
        if is_correction(text):
            e.state.reject(e.state.last_assistant_answer)
        elif verification.status == "PASS":
            e.state.accept(answer)
        e.state.update(text, answer, plan.answer_type, parsed, verification.score, reference)
        e.state.save(e.state_path)
        e._commit_memory(text, answer, context, verification)
        e._update_frame(context, reference)

        trace = TurnTrace(
            user_text=text, intent=context.intent, topic=e.state.current_topic,
            reference=reference, memory_count=len(memory), knowledge_count=len(knowledge),
            reasoning_status=getattr(chain_result, "status", "NOT_RUN"),
            answer_status=getattr(synthesis, "status", plan.answer_type),
            verification_status=verification.status, confidence=float(verification.score),
            sources=list(getattr(synthesis, "sources", []) or []),
            elapsed_ms=round((datetime.now() - started).total_seconds() * 1000, 2),
        )
        e.last_trace = trace
        e.turn_traces.append(trace.__dict__)
        e.turn_traces = e.turn_traces[-50:]
        self._emit("language_analysis", {"intent": context.intent, "confidence": context.confidence, "entities": context.entities, "constraints": context.constraints, "canonical": True})
        self._emit("cognitive_cycle", {"intent": context.intent, "confidence": context.confidence, "decision": {"chosen": "respond"}, "canonical": True})
        self._emit("plan_created", {"goal": text, "version": 1, "steps": [str(getattr(s, "title", s)) for s in plan.steps], "canonical": True})
        self._emit("reflection", {"score": verification.score, "canonical": True})
        self._emit("learning_update", {"score": verification.score, "canonical": True})
        self._emit("response_generated", {"goal": text, "route": "unified_cognitive_response", "mode": "UNKNOWN" if answer.startswith("UNKNOWN:") else ("DIRECT_FACT" if knowledge else "DIRECT"), "score": verification.score, "verified": verification.status == "PASS", "canonical": True})
        self._emit("canonical_cognitive_turn", trace.__dict__)
        return answer
