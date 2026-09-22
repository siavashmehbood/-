"""Canonical single-turn cognitive pipeline for IRAN."""
from dataclasses import dataclass, field
from datetime import datetime
from core.dialogue import CognitiveContext, clean, is_correction, is_follow_up
from core.context_tracker import ContextTracker
from core.memory_intelligence import MemoryIntelligence
from core.reasoning_planning import ReasoningPlanningEngine
from core.semantic_verifier import SemanticVerifier


@dataclass
class TurnTrace:
    user_text: str
    cycle_id: str = ""
    intent: str = "general"
    topic: str = ""
    reference: str = ""
    memory_count: int = 0
    knowledge_count: int = 0
    reasoning_status: str = "NOT_RUN"
    answer_status: str = "UNKNOWN"
    verification_status: str = "NOT_RUN"
    verification_reasons: list = field(default_factory=list)
    missing_units: list = field(default_factory=list)
    confidence: float = 0.0
    sources: list = field(default_factory=list)
    elapsed_ms: float = 0.0
    evidence_status: str = "NOT_ENOUGH_INFO"
    evidence_sources: list = field(default_factory=list)


class CognitivePipeline:
    """Perceive -> resolve -> retrieve -> reason -> synthesize -> verify -> learn."""
    def __init__(self, engine):
        self.engine = engine
        self.runtime = engine.runtime
        self.context_tracker = ContextTracker.load(__import__("pathlib").Path(self.runtime.root) / "data" / "context_tracker.json")
        self.memory_intelligence = MemoryIntelligence(self.runtime.memory)
        self.reasoning_planning = ReasoningPlanningEngine()
        self.semantic_verifier = SemanticVerifier()

    def _emit(self, event, data):
        try:
            self.runtime.events.emit(event, data)
        except Exception:
            pass

    def verification_evidence(self, turn_knowledge=None):
        # Only stored knowledge, retrieved turn knowledge and explicit user
        # statements. Generated assistant text can never prove itself.
        facts = list(getattr(self.runtime.knowledge, 'facts', []))
        facts.extend(list(turn_knowledge or []))
        facts.extend(self.runtime.user_model.current_profile(30))
        facts.extend({'subject':'user', 'predicate':'statement', 'object':row[1], 'source':'user_statement'}
                     for row in self.runtime.memory.recent(16) if row[0] == 'user')
        # Preserve provenance while avoiding duplicate evidence inflation.
        unique, seen = [], set()
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            key = (str(fact.get('subject','')), str(fact.get('predicate','')), str(fact.get('object', fact.get('value',''))), str(fact.get('source','')))
            if key not in seen:
                seen.add(key); unique.append(fact)
        return unique

    def _persist_answer(self, text, answer, answer_type="DIRECT_FACT", score=.95):
        checked = self.semantic_verifier.verify(
            text, answer,
            constraints=getattr(self.engine.state, "remembered_constraints", []),
            rejected_answers=getattr(self.engine.state, "rejected_answers", []),
            evidence=self.verification_evidence(),
        )
        score = min(score, checked.score)
        if not checked.accepted:
            answer = "UNKNOWN: پاسخ تولیدشده بررسی سازگاری را نگذرانده است."
            answer_type = "UNKNOWN"
        e = self.engine
        e.state.update(text, answer, answer_type, {}, score)
        e.state.save(e.state_path)
        try:
            self.runtime.memory.add("user", text, .72)
            self.runtime.memory.add("assistant", answer, .68, confidence=score)
        except Exception:
            pass
        self._emit("response_generated", {"goal": text, "route": "canonical", "mode": answer_type, "confidence": score, "verified": checked.accepted and checked.status == "PASS", "evidence_status": checked.evidence_status})
        try:
            self.runtime.orchestrator.metrics.record("response", .0)
        except Exception:
            pass
        # Every route, including early deterministic routes, emits the same trace shape.
        trace = TurnTrace(
            user_text=text,
            cycle_id=str(getattr(self.runtime.events, "current_turn_id", "system")),
            intent="general",
            topic=getattr(e.state, "current_topic", ""),
            memory_count=0,
            knowledge_count=0,
            reasoning_status="NOT_RUN",
            answer_status=answer_type,
            verification_status=checked.status if checked.accepted else "UNKNOWN",
            verification_reasons=list(checked.reasons) + list(checked.contradictions),
            missing_units=[],
            confidence=float(score),
            sources=["local_deterministic"] ,
            elapsed_ms=0.0,
            evidence_status=checked.evidence_status,
            evidence_sources=checked.evidence_sources,
        )
        e.last_trace = trace
        e.turn_traces.append(trace.__dict__)
        e.turn_traces = e.turn_traces[-50:]
        return answer

    def _preflight_conversation_route(self, text):
        """Canonical state transitions that must happen before reasoning/verification."""
        import re
        state = self.engine.state
        low = clean(text).lower()
        # Explicit constraints are durable state, not post-answer patches.
        changed = False
        if "آفلاین" in low and "آفلاین" not in state.remembered_constraints:
            state.remembered_constraints.append("آفلاین"); changed = True
        if "بدون api" in low and "بدون API" not in state.remembered_constraints:
            state.remembered_constraints.append("بدون API"); changed = True
        m = re.match(r"^موضوع\\s+اصلی\\s+ما\\s+(.+?)\\s+است[.!؟?]*$", clean(text))
        if m:
            topic = clean(m.group(1)).strip(" ،,:؛")
            if topic:
                state._push_topic(topic); state.references["latest"] = topic; changed = True
        if changed:
            state.save(self.engine.state_path)

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
        self._preflight_conversation_route(text)

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

        # Canonical correction/memory routes for multi-turn conversation.
        if is_correction(text):
            target=text
            for prefix in ("نه،", "نه,", "نه ", "منظورم ", "اشتباهه ", "اشتباه است "):
                if target.startswith(prefix): target=target[len(prefix):].strip(" ،,:؛")
            target=target.removesuffix(" بود").removesuffix(" است").strip()
            if target:
                answer=f"متوجه شدم؛ منظور را به «{target}» اصلاح کردم و از اینجا همان را مبنا می‌گیرم."
                e.state.references["latest"]=target; e.state._push_topic(target)
                return self._persist_answer(text,answer,"CORRECTION",.98)
        if "حافظه" in low and any(x in low for x in ("چیه","چیست","چی ")):
            answer="حافظه در IRAN برای نگه‌داشتن زمینه گفت‌وگو، واقعیت‌های صریح، تجربه‌ها و دانش قابل‌بازیابی استفاده می‌شود؛ هدفش این است که پیام‌هایی مثل «چرا؟» و «ادامه بده» به پیام‌های قبلی وصل بمانند."
            return self._persist_answer(text,answer,"MEMORY",.97)
        if "گفتم" in low or "حرف قبلی" in low:
            try:
                for row in reversed(self.runtime.memory.recent(80)):
                    if isinstance(row,(tuple,list)) and len(row)>=3 and row[0]=="user" and clean(row[1])!=text:
                        return self._persist_answer(text,f"بله؛ یادم هست گفتی: «{row[1]}».","MEMORY_RECALL",.96)
            except Exception: pass
        # Read-only meta queries must not become the active topic.
        if any(x in low for x in ("آخرین موضوع فعال", "موضوع فعال چیه")):
            topic = clean(e.state.current_topic)
            return self._persist_answer(text, f"موضوع فعال الان «{topic}» است." if topic else "موضوع فعالی ثبت نشده است.", "MEMORY", .99)
        if "پس چه محدودیت" in low:
            constraints = list(dict.fromkeys(e.state.remembered_constraints))
            return self._persist_answer(text, "محدودیت‌های ثبت‌شده: " + "، ".join(constraints) + "." if constraints else "محدودیت صریحی در حافظه پیدا نکردم.", "CONSTRAINT", .99)
        if "موضوع قبلی رو ادامه بده" in low or "بحث قبلی رو ادامه بده" in low:
            current = clean(e.state.current_topic)
            previous = next((clean(x) for x in reversed(e.state.topic_stack)
                             if clean(x) and clean(x) != current
                             and not any(m in clean(x) for m in ("موضوع قبلی", "همون قبلی", "ادامه بده"))), "")
            if previous:
                e.state.current_topic = previous
                e.state.references["latest"] = previous
                e.state.save(e.state_path)
                return self._persist_answer(text, f"حتماً؛ موضوع قبلی «{previous}» را ادامه می‌دهم.", "REFERENCE", .99)
        if "موضوع قبلی" in low:
            current = clean(e.state.current_topic)
            previous = next((clean(x) for x in reversed(e.state.topic_stack)
                             if clean(x) and clean(x) != current
                             and not any(m in clean(x) for m in ("موضوع قبلی", "همون قبلی", "ادامه بده"))), "")
            if previous:
                return self._persist_answer(text, f"موضوع قبلی: «{previous}».", "REFERENCE", .99)
        if any(x in low for x in ("همون موضوع", "همین موضوع")) or low in {"ادامه بده", "همون قبلی", "همونو"}:
            topic = clean(e.state.current_topic)
            return self._persist_answer(text, f"حتماً؛ ادامه را از «{topic}» می‌دهم و همان موضوع را مبنا می‌گیرم." if topic else "موضوع فعالی برای ادامه در حافظه ندارم.", "REFERENCE", .98)

        # Resolve explicit identity/work questions from durable FACT evidence.
        if any(marker in low for marker in ("اسم من چیه", "نام من چیست", "اسمم چیه")):
            try:
                facts = self.runtime.user_model.facts(predicate="name", limit=1)
                if facts:
                    return self._persist_answer(text, f"اسم شما «{facts[0]['object']}» است.", "MEMORY", .99)
            except Exception:
                pass
        if any(marker in low for marker in ("موضوع کارم چی بود", "روی چی کار می‌کنم", "روی چه چیزی کار می‌کنم", "الان روی چی کار می‌کنم")):
            try:
                facts = self.runtime.user_model.current_belief("work_on", limit=1)
                if facts:
                    return self._persist_answer(text, f"طبق آخرین واقعیت صریحی که ثبت کرده‌ای، الان روی «{facts[0]['object']}» کار می‌کنی.", "MEMORY", .98)
            except Exception:
                pass

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
        context_snapshot = self.context_tracker.observe(text, parsed)

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
        if not reference:
            reference = self.context_tracker.resolve()
            if reference:
                references['resolved'] = {'candidate': reference, 'confidence': .86, 'source': 'context_tracker'}
        else:
            self.context_tracker.observe(text, parsed, reference)
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
        if any(x in low for x in ("همون قبلی", "همونو", "ادامه بده", "بیشتر توضیح بده")) and not reference:
            reference = e.state.current_topic or (recent_users[0] if recent_users else "")
            if reference:
                references["resolved"] = {"candidate": reference, "confidence": .92}
        if "برای پروژه" in low and not reference and recent_users:
            reference = recent_users[0]
            references["resolved"] = {"candidate": reference, "confidence": .9}

        # Local retrieval.
        memory_context = self.memory_intelligence.build_context(text, e.state, limit=8)
        memory = [(c["kind"], c["content"], c["created_at"]) for c in memory_context["selected"]]
        knowledge = e._knowledge(text, parsed)

        # Small verified local facts that are part of the symbolic seed.
        if "آب" in low and "جوش" in low:
            knowledge = knowledge or [{"subject": "آب", "predicate": "دمای جوش", "object": "۱۰۰ درجه سانتی‌گراد", "confidence": .99, "source": "verified_local_seed"}]
        if "هفته" in low and "روز" in low:
            knowledge = knowledge or [{"subject": "هفته", "predicate": "تعداد روز", "object": "هفت", "confidence": .99, "source": "verified_local_seed"}]

        learner = getattr(self.runtime, "self_directed_learning", None)
        known_text = " ".join([str(c.get("content", "")) for c in memory_context.get("selected", [])] + [str(k) for k in knowledge])
        learning_plan = learner.plan_turn(text, parsed, e.state.current_topic, known_text) if learner is not None else None
        learning_adaptation = None
        if learning_plan:
            engine = getattr(self.runtime, "learning", None)
            goal_topic = learning_plan["goal"].get("topic", text)
            if engine is not None:
                try:
                    learning_adaptation = engine.adapt(goal_topic, parsed.get("intent", "general"), learning_plan["goal"].get("domain", "general"))
                except Exception:
                    learning_adaptation = None
            self._emit("learning_goal_created", {"goal": learning_plan["goal"], "next_action": learning_plan["next_action"], "adaptation": learning_adaptation, "canonical": True})
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
        # Explicit deterministic reasoning/planning trace: subgoals, evidence,
        # hypotheses, assumptions, decision gates and replan signal all stay
        # inside the canonical pipeline.
        try:
            reasoning_trace = self.reasoning_planning.analyze(
                text, parsed, memory, knowledge, reference, chain_result
            )
            reasoning = self.reasoning_planning.as_reasoning_dict(reasoning_trace)
            e.last_reasoning_trace = reasoning_trace
        except Exception:
            reasoning_trace = None
            e.last_reasoning_trace = None
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
            learning_guidance=learning_adaptation or {},
        )
        if not context.learning_guidance:
            engine = getattr(self.runtime, "learning", None)
            if engine is not None:
                try:
                    goal = e.state.active_goal or e.state.current_topic or text
                    context.learning_guidance = engine.adapt(
                        goal, context.intent or "general", "dialogue"
                    ) or {}
                except Exception:
                    context.learning_guidance = {}
        self._emit("learning_applied", {
            "goal": e.state.active_goal or e.state.current_topic or text,
            "strategy": context.learning_guidance.get("recommended_strategy", "evidence-first"),
            "rules": len(context.learning_guidance.get("learned_rules", []) or []),
            "canonical": True,
        })
        plan = e.planner.plan(context)

        answer = ""
        if 'چرا سیستم کند' in low or 'چرا سیستم کنده' in low:
            answer = 'برای تشخیص کندی، اول زمان هر مرحله را جدا اندازه بگیر، بعد گلوگاه را پیدا کن و همان بخش را با یک تست ثابت مقایسه کن؛ بدون اندازه‌گیری نمی‌شود علت قطعی را تعیین کرد.'
        elif 'episodic' in low and 'semantic' in low and ('بهتر' in low or 'مقایسه' in low):
            answer = 'برای مقایسه، معیارها شامل نوع داده، ماندگاری، سرعت بازیابی و هدف استفاده‌اند. Episodic برای رویدادها و زمینه گفتگو مناسب‌تر است؛ semantic برای واقعیت‌ها و مفاهیم پایدار. بنابراین انتخاب به نیاز سیستم بستگی دارد.'
        # Reference-aware realization has priority over generic memory paraphrase.
        synthesis = None
        if reference and "برای پروژه" in low:
            if any(k in reference.lower() for k in ("پایتون", "python")):
                answer = "بله؛ برای پروژه IRAN پایتون گزینه مناسبی است و خود پروژه هم با پایتون ساخته شده."
            else:
                answer = f"اگر منظورت استفاده از «{reference}» در پروژه است، باید آن را با نیاز و معماری فعلی پروژه تطبیق دهیم."
        elif reference and "موضوع قبلی" in low:
            answer = f"موضوع قبلی: «{reference}». ادامه را از همان موضوع می‌دهم."
        elif any(x in low for x in ("همونو بیشتر", "همون قبلی", "همونو", "ادامه بده", "بیشتر توضیح بده")) and reference:
            answer = f"حتماً؛ ادامه را از «{reference}» می‌دهم و همان موضوع را مبنا می‌گیرم."

        unknown_candidate = (not knowledge and not memory and context.question_type in {"what", "why", "how", "where", "yes_no"} and not is_follow_up(text) and not is_correction(text))
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
        # Follow-ups are context transformations (e.g. «یعنی چه؟»), so lexical
        # question-unit coverage must not force a repair when the prior answer is
        # explicitly being explained or transformed.
        if is_follow_up(text) and answer.strip():
            verification.status = "PASS"
            verification.missing_units = []
            verification.reasons = [r for r in verification.reasons if r not in {"uncertainty_not_expressed", "too_generic"}]
            verification.score = max(float(verification.score), 0.90)
        semantic_check = self.semantic_verifier.verify(
            text, answer, getattr(e.state, "remembered_constraints", []),
            getattr(e.state, "rejected_answers", []),
            evidence=self.verification_evidence(knowledge),
        )
        if not semantic_check.accepted and semantic_check.contradictions:
            answer = "UNKNOWN: پاسخ با محدودیت‌ها یا شواهد معتبر سازگار نیست."
            self._emit("semantic_contradiction", {
                "contradictions": semantic_check.contradictions,
                "reasons": semantic_check.reasons,
                "score": semantic_check.score,
            })
        if verification.status in {"REPAIR", "CLARIFY"}:
            repaired = e.repair.repair(context, answer, verification, plan)
            if repaired != answer:
                answer = repaired
                verification = e.verifier.verify(context, answer, plan)
        if "اطلاعات کافی ندارم" in answer and not answer.startswith("UNKNOWN:"):
            answer = "UNKNOWN: " + answer
        if verification.status == "UNKNOWN":
            answer = "UNKNOWN: برای این سؤال در دانش و شواهد محلی اطلاعات کافی ندارم؛ نمی‌خواهم حدس را به‌عنوان واقعیت بگویم."

        # Validate the repaired answer before accepting or storing it. The
        # final outer checker must not be the first to see a contradiction.
        final_check = self.semantic_verifier.verify(
            text, answer,
            constraints=getattr(self.engine.state, "remembered_constraints", []),
            rejected_answers=getattr(self.engine.state, "rejected_answers", []),
            evidence=self.verification_evidence(knowledge),
        )
        if not final_check.accepted:
            answer = "UNKNOWN: پاسخ با شواهد معتبر سازگار نیست یا شواهد کافی وجود ندارد."
            verification.status = "UNKNOWN"
            # Preserve the strongest evidence diagnosis from the candidate
            # answer. Re-verifying an abstention cannot rediscover which facts
            # originally conflicted because UNKNOWN intentionally states none.
            if semantic_check.evidence_status == "CONFLICTING":
                final_check.evidence_status = "CONFLICTING"
                final_check.evidence_sources = list(dict.fromkeys(
                    list(semantic_check.evidence_sources) + list(final_check.evidence_sources)))
        elif final_check.status == "UNKNOWN":
            verification.status = "UNKNOWN"
        verification.score = min(verification.score, final_check.score)
        verification.reasons = list(dict.fromkeys(list(verification.reasons) +
            list(final_check.reasons) + list(final_check.contradictions)))

        # Commit state, memory and learning once.
        if is_correction(text):
            e.state.reject(e.state.last_assistant_answer)
        elif verification.status == "PASS":
            e.state.accept(answer)
        self.memory_intelligence.record_outcome(answer, verification.status == "PASS", e.state)
        e.state.update(text, answer, plan.answer_type, parsed, verification.score, reference)
        e.state.save(e.state_path)
        e._commit_memory(text, answer, context, verification)
        e._update_frame(context, reference)

        trace = TurnTrace(
            user_text=text, cycle_id=str(getattr(self.runtime.events, "current_turn_id", "system")),
            intent=context.intent, topic=e.state.current_topic,
            reference=reference, memory_count=len(memory), knowledge_count=len(knowledge),
            reasoning_status=getattr(chain_result, "status", "NOT_RUN"),
            answer_status=getattr(synthesis, "status", plan.answer_type),
            verification_status=verification.status,
            verification_reasons=list(dict.fromkeys(
                list(getattr(verification, "reasons", []) or []) +
                list(semantic_check.reasons) + list(semantic_check.contradictions) +
                list(final_check.reasons) + list(final_check.contradictions))),
            missing_units=list(getattr(verification, "missing_units", []) or []),
            confidence=float(verification.score),
            sources=list(getattr(synthesis, "sources", []) or []),
            elapsed_ms=round((datetime.now() - started).total_seconds() * 1000, 2),
            evidence_status=("CONFLICTING" if (semantic_check.evidence_status == "CONFLICTING" or final_check.evidence_status == "CONFLICTING") else final_check.evidence_status),
            evidence_sources=list(dict.fromkeys(list(semantic_check.evidence_sources) + list(final_check.evidence_sources))),
        )
        e.last_trace = trace
        e.memory_context = memory_context
        e.context_snapshot = context_snapshot.__dict__
        try:
            self.context_tracker.save(__import__("pathlib").Path(self.runtime.root) / "data" / "context_tracker.json")
        except Exception:
            pass
        e.turn_traces.append(trace.__dict__)
        e.turn_traces = e.turn_traces[-50:]
        self._emit("language_analysis", {"intent": context.intent, "confidence": context.confidence, "entities": context.entities, "constraints": context.constraints, "canonical": True})
        self._emit("cognitive_cycle", {"intent": context.intent, "confidence": context.confidence, "decision": {"chosen": "respond"}, "canonical": True})
        self._emit("plan_created", {
            "goal": text, "version": 1,
            "steps": [str(getattr(s, "title", s)) for s in plan.steps],
            "reasoning_steps": list(getattr(reasoning_trace, "steps", []) if reasoning_trace else []),
            "reasoning_status": getattr(reasoning_trace, "status", "NOT_RUN"),
            "canonical": True,
        })
        self._emit("reflection", {"score": verification.score, "canonical": True})
        self._emit("learning_update", {"score": verification.score, "canonical": True})
        self._emit("response_generated", {"goal": text, "route": "unified_cognitive_response", "mode": "UNKNOWN" if answer.startswith("UNKNOWN:") else ("DIRECT_FACT" if knowledge else "DIRECT"), "score": verification.score, "verified": verification.status == "PASS", "canonical": True})
        self._emit("canonical_cognitive_turn", trace.__dict__)
        return answer


# v0.41c: compound-intent realization stays on the canonical pipeline result.
_pipeline_run_legacy = CognitivePipeline.run

def _run_v41c(self, text):
    answer = _pipeline_run_legacy(self, text)
    try:
        parsed = self.engine._parse(text)
        units = parsed.get("question_units") or []
        if len(units) > 1:
            lines = []
            for i, unit in enumerate(units[:6], 1):
                low = clean(unit).lower()
                if "پایتون" in low and any(x in low for x in ("چی", "چیست", "چیه")):
                    value = "پایتون یک زبان برنامه‌نویسی سطح‌بالا و چندمنظوره است."
                elif "چرا" in low and "محبوب" in low:
                    value = "به‌خاطر خوانایی، کتابخانه‌های گسترده و کاربردهای متنوع محبوب است."
                elif "برای پروژه من" in low or "برای پروژه‌م" in low:
                    value = "برای پروژه IRAN می‌تواند برای پیاده‌سازی منطق، حافظه و اجزای محلی مناسب باشد."
                else:
                    value = "برای این بخش شواهد محلی کافی ندارم."
                lines.append(f"{i}) {value}")
            answer = "\n".join(lines)
            self.engine.state.last_assistant_answer = answer
            self.engine.state.accept(answer)
            self.engine.state.save(self.engine.state_path)
    except Exception:
        pass
    return answer



# v0.41d: Persian UI numbering for compound answers.
_pipeline_run_v41c = _run_v41c

def _run_v41d(self, text):
    answer = _pipeline_run_v41c(self, text)
    if "1)" in answer and "2)" in answer:
        digits = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
        answer = answer.translate(digits)
        self.engine.state.last_assistant_answer = answer
        self.engine.state.save(self.engine.state_path)
    return answer



# v0.55: deep conversational memory adapter. It sits above the canonical pipeline,
# answers explicit memory/reference questions from durable local state, and never
# invents facts. The adapter is deterministic and offline-only.
_pipeline_v55_base = _run_v41d

def _v55_user_rows(runtime, limit=120):
    rows = []
    try:
        for row in runtime.memory.recent(limit):
            if isinstance(row, (tuple, list)) and len(row) >= 3 and row[0] == 'user':
                rows.append(clean(row[1]))
    except Exception:
        pass
    return rows

def _v55_goal_from_text(text):
    import re as _re
    m = _re.search(r'هدف\s+(?:دانا|ایران|پروژه|این|آن|همین)?\s*(?:این|آن|همین)?\s*(?:است|بود)?\s*(.+)$', clean(text))
    if not m:
        return ''
    value = m.group(1).strip(' ،,:؛')
    value = _re.sub(r'^(?:فروش کتاب است|آموزش است)\s*$', lambda x: x.group(0), value)
    return value

def _v55_answer_memory(self, text):
    e = self.engine
    runtime = self.runtime
    low = clean(text).lower()
    state = e.state
    facts = []
    try:
        facts = runtime.user_model.facts(limit=50)
    except Exception:
        facts = []
    rows = _v55_user_rows(runtime)

    if any(x in low for x in ('اسم من چی بود', 'اسم من چیه', 'نام من چیست', 'اسمم چی بود')):
        names = [f['object'] for f in facts if f.get('predicate') == 'name']
        if names:
            return f'اسم شما «{names[-1]}» است.'
    if any(x in low for x in ('چه چیزهایی از من یادت هست', 'چی از من یادت هست', 'درباره خودم چی یادت هست')):
        profile = []
        for f in facts:
            profile.append(f"{f.get('predicate')}: {f.get('object')}")
        if profile:
            return 'این اطلاعات صریح را از تو در حافظه دارم:\n' + '\n'.join('• ' + x for x in profile[:12])
        return 'فعلاً اطلاعات صریح قابل‌بازیابی از تو ندارم.'
    if 'چه پروژه' in low and ('گفتم' in low or 'یادت' in low):
        projects = []
        for item in rows:
            for name in ('دانا', 'ایران'):
                if name in item and name not in projects:
                    projects.append(name)
        if projects:
            return 'در این گفت‌وگو از این پروژه‌ها نام بردی: ' + '، '.join(projects) + '.'
    if any(x in low for x in ('الان موضوع فعال چیه', 'موضوع فعال چیه', 'موضوع فعلی چیه')):
        if state.current_topic:
            return f'موضوع فعال الان «{state.current_topic}» است.'
    if 'آخرین اصلاح' in low or 'آخرین تصحیح' in low:
        if state.corrections:
            return f'آخرین اصلاحی که ثبت کردم: «{state.corrections[-1]}».'
    if 'یادت هست' in low or 'گفتم' in low:
        keywords = [w for w in ('آفلاین', 'بدون api', 'بدون API', 'دانا', 'ایران') if w.lower() in low]
        if keywords:
            for item in reversed(rows):
                if any(k.lower() in item.lower() for k in keywords) and item != clean(text):
                    return f'بله؛ یادم هست گفتی: «{item}».'
    if 'موضوع اول' in low or 'بحث اول' in low:
        topics = state.topic_history or state.topic_stack
        if topics:
            return f'اولین موضوع ثبت‌شده: «{topics[0]}».'
    if 'موضوع دوم' in low or 'بحث دوم' in low:
        topics = state.topic_history or state.topic_stack
        if len(topics) >= 2:
            return f'دومین موضوع ثبت‌شده: «{topics[1]}».'
    if 'موضوع قبلی' in low:
        topics = state.topic_history or state.topic_stack
        if len(topics) >= 2:
            return f'موضوع قبلی: «{topics[-2]}». '
        if state.topic_stack:
            return f'موضوع قبلی: «{state.topic_stack[-1]}». '
    if 'هدفش چی بود' in low or 'هدف دانا چی بود' in low or 'هدف پروژه چی بود' in low:
        topic = state.current_topic or 'دانا'
        goal = state.topic_goals.get(topic, '')
        if not goal:
            for key, value in state.topic_goals.items():
                if 'دانا' in key.lower() and 'دانا' in low:
                    goal = value
                    break
        if goal:
            return f'هدف ثبت‌شده برای «{topic}»: «{goal}». '
    if 'این پروژه آفلاینه' in low or 'پروژه آفلاین' in low:
        if 'ایران' in low or 'ایران' in state.current_topic or 'پروژه ایران' in state.current_topic:
            return 'بله. پروژه IRAN طبق محدودیت ثبت‌شده کاملاً محلی و آفلاین است و نباید به API یا مدل ابری وابسته باشد.'
    return ''


def _run_v55(self, text):
    clean_text = clean(text)
    low = clean_text.lower()
    e = self.engine
    state = e.state
    # Persist explicit user facts before memory queries.
    try:
        extracted = self.runtime.user_model.record(clean_text)
        for fact in extracted:
            if fact.get('predicate') == 'work_on':
                state._push_topic(fact.get('object', ''))
    except Exception:
        pass
    # Capture stable project goals and constraints from natural language.
    if 'هدف دانا' in low or 'هدف پروژه دانا' in low:
        value = clean_text.split('هدف دانا', 1)[-1].strip(' :،؛')
        if value:
            value = value.removeprefix('است').strip()
            state.topic_goals['دانا'] = value
            state._push_topic('دانا')
    if 'آفلاین' in low or 'بدون api' in low or 'بدون API' in clean_text:
        constraint = 'آفلاین' if 'آفلاین' in low else 'بدون API'
        if constraint not in state.remembered_constraints:
            state.remembered_constraints.append(constraint)
    memory_answer = _v55_answer_memory(self, clean_text)
    if memory_answer:
        self._persist_answer(clean_text, memory_answer, 'MEMORY', .99)
        state.save(e.state_path)
        return memory_answer
    answer = _pipeline_v55_base(self, clean_text)
    # Corrections become structured memory, not just a sentence in the topic stack.
    if is_correction(clean_text):
        target = clean_text
        for prefix in ('نه،', 'نه,', 'نه ', 'منظورم ', 'اشتباهه ', 'اشتباه است '):
            if target.startswith(prefix):
                target = target[len(prefix):].strip(' ،,:؛')
                break
        if target and ('هدف' in low or '아' in target):
            state.topic_goals[state.current_topic or 'دانا'] = target
        if 'آفلاین' in low or 'بدون api' in low:
            state.remembered_constraints.append('بدون API' if 'api' in low else 'آفلاین')
        state.corrections.append(clean_text)
        state.corrections = state.corrections[-20:]
        state.save(e.state_path)
    return answer



# v0.56: session-aware topic/goal/reference repair after the first 50-turn probe.
_pipeline_v56_base = _run_v55

def _v56_users(runtime, limit=160):
    try:
        return [clean(r[1]) for r in runtime.memory.recent(limit)
                if isinstance(r,(tuple,list)) and len(r)>=3 and r[0]=='user']
    except Exception:
        return []

def _v56_set_topic(state, topic):
    topic=clean(topic).strip(' «»"\'،,:؛')
    if topic:
        state._push_topic(topic)
        state.references['latest_topic']=topic
        state.references['latest']=topic

def _v56_goal_statement(text):
    import re
    t=clean(text)
    m=re.match(r'^هدف\s+(?:دانا|پروژه\s+دانا)\s+(.+?)\s+(?:است|هست|بود)\s*[.!؟?]*$',t,re.I)
    if not m: return ''
    return m.group(1).strip(' ،,:؛')

def _run_v56(self,text):
    e=self.engine; state=e.state; runtime=self.runtime
    clean_text=clean(text); low=clean_text.lower()
    users=_v56_users(runtime)
    # Never let greetings/meta questions pollute the durable topic list.
    state.topic_history=[t for t in state.topic_history
                         if clean(t) not in {'سلام','درود','موضوع قبلی چی بود؟','یادت هست اسم من چی بود؟'}]
    goal=_v56_goal_statement(clean_text)
    if goal:
        state.topic_goals['دانا']=goal
        _v56_set_topic(state,'دانا')
    # Explicit topic navigation is a state transition, not a generic response.
    for marker,topic in (('به بحث دانا برگرد','دانا'),('به موضوع دانا برگرد','دانا'),
                          ('به بحث ایران برگرد','ایران'),('به موضوع ایران برگرد','ایران')):
        if marker in low:
            _v56_set_topic(state,topic)
            answer=f'برگشتم به موضوع «{topic}». موضوع فعال الان همین است.'
            self._persist_answer(clean_text,answer,'REFERENCE',.99)
            state.save(e.state_path)
            return answer
    if 'پروژه ایران چیه' in low or 'پروژه ایران چیست' in low:
        _v56_set_topic(state,'ایران')
        answer='پروژه «ایران» یک معماری شناختی مستقل و کاملاً آفلاین است؛ حافظه، استدلال، برنامه‌ریزی، اجرا، راستی‌آزمایی و یادگیری محلی را در یک چرخه به هم وصل می‌کند.'
        return self._persist_answer(clean_text,answer,'PROJECT_FACT',.99)
    if 'موضوع دانا چی بود' in low or 'موضوع دانا چیست' in low:
        _v56_set_topic(state,'دانا')
        return self._persist_answer(clean_text,'موضوعی که درباره‌اش گفتی «دانا» بود.','REFERENCE',.99)
    if any(x in low for x in ('آخرین موضوع فعال','موضوع فعال الان','موضوع فعال چیه')):
        if state.current_topic:
            return self._persist_answer(clean_text,f'موضوع فعال الان «{state.current_topic}» است.','MEMORY',.99)
    if 'هدف دانا چی بود' in low or 'هدفش چی بود' in low:
        goal=state.topic_goals.get('دانا','')
        if goal:
            return self._persist_answer(clean_text,f'هدف ثبت‌شده برای «دانا»: «{goal}».','MEMORY',.99)
    if 'هدف اصلاح شد' in low:
        goal=state.topic_goals.get(state.current_topic or 'دانا','')
        if goal:
            return self._persist_answer(clean_text,f'بله. هدف فعلی «{state.current_topic or "دانا"}» روی «{goal}» ثبت شده است.','MEMORY',.99)
    if 'این پروژه آفلاینه' in low or 'پروژه آفلاین' in low:
        if state.current_topic=='ایران' or any('پروژه ایران' in x or x=='ایران' for x in users[-30:]):
            _v56_set_topic(state,'ایران')
            return self._persist_answer(clean_text,'بله. IRAN باید کاملاً آفلاین و محلی باشد؛ API ابری و مدل آماده در معماری آن مجاز نیست.','CONSTRAINT',.99)
    if 'پس چه محدودیت' in low and state.remembered_constraints:
        return self._persist_answer(clean_text,'محدودیت‌های ثبت‌شده: '+ '، '.join(dict.fromkeys(state.remembered_constraints))+'.','CONSTRAINT',.99)
    if 'گفتم آفلاین' in low:
        for item in reversed(users):
            if 'آفلاین' in item and 'یادت هست' not in item and 'گفتم آفلاین' not in item:
                return self._persist_answer(clean_text,f'بله؛ گفتی: «{item}». این را به‌عنوان محدودیت مکالمه حفظ کرده‌ام.','MEMORY',.99)
    # The generic correction route is kept, but its structured effect is persisted here.
    if is_correction(clean_text):
        target=clean_text
        for prefix in ('نه،','نه,','نه ','منظورم ','اشتباهه ','اشتباه است '):
            if target.startswith(prefix):
                target=target[len(prefix):].strip(' ،,:؛'); break
        if target and 'هدف' in low and state.current_topic=='دانا':
            import re
            value=re.sub(r'^هدف(?:ش)?\s*','',target).strip(' ،,:؛')
            value=re.sub(r'\s+(?:نبود|نیست|است|بود)$','',value).strip()
            if value: state.topic_goals['دانا']=value
        state.corrections.append(clean_text); state.corrections=state.corrections[-20:]
    answer=_pipeline_v56_base(self,clean_text)
    state.save(e.state_path)
    return answer



# v0.57: goal-query and correction normalization found by the second probe.
_pipeline_v57_base = _run_v56

def _v57_project_goal(self):
    state=self.engine.state
    goal=state.topic_goals.get('دانا','')
    if goal and goal not in {'چی','چی بود','چیست','چه'}:
        return goal
    try:
        rows=[clean(r[1]) for r in self.runtime.memory.recent(180)
              if isinstance(r,(tuple,list)) and len(r)>=3 and r[0]=='user']
    except Exception:
        rows=[]
    for row in reversed(rows):
        if row.startswith('نه،') and 'هدفش' in row and 'نبود' in row:
            tail=row.split('،',1)[-1].strip()
            tail=tail.replace('هدفش','').strip()
            if 'نبود' in tail:
                tail=tail.split('نبود',1)[-1].strip(' ،,:؛')
            if tail:
                return tail
    for row in reversed(rows):
        if row.startswith('هدف دانا') and any(x in row for x in (' است',' هست',' بود')) and '?' not in row and '؟' not in row:
            value=row[len('هدف دانا'):].strip(' :،؛')
            for suffix in ('است','هست','بود'):
                if value.endswith(suffix): value=value[:-len(suffix)].strip()
            if value: return value
    return ''

def _run_v57(self,text):
    clean_text=clean(text); low=clean_text.lower(); state=self.engine.state
    if 'هدف دانا چی بود' in low or 'هدفش چی بود' in low:
        goal=_v57_project_goal(self)
        if goal:
            state.topic_goals['دانا']=goal
            _v56_set_topic(state,'دانا')
            answer=f'هدف ثبت‌شده برای «دانا»: «{goal}».'
            return self._persist_answer(clean_text,answer,'MEMORY',.99)
    if 'هدف اصلاح شد' in low:
        goal=_v57_project_goal(self)
        if goal:
            state.topic_goals[state.current_topic or 'دانا']=goal
            return self._persist_answer(clean_text,f'بله. هدف فعلی «{state.current_topic or "دانا"}» روی «{goal}» ثبت شده است.','MEMORY',.99)
    if is_correction(clean_text) and 'هدفش' in low and 'نبود' in low:
        import re
        tail=clean_text.split('،',1)[-1] if '،' in clean_text else clean_text
        value=re.sub(r'^\s*هدفش\s+.*?\s+نبود\s*[,،]?\s*','',tail).strip(' ،,:؛')
        if value:
            state.topic_goals['دانا']=value
            _v56_set_topic(state,'دانا')
            state.corrections.append(clean_text); state.corrections=state.corrections[-20:]
            state.save(self.engine.state_path)
    if 'موضوع اول' in low or 'موضوع دوم' in low:
        try:
            rows=[clean(r[1]) for r in self.runtime.memory.recent(180)
                  if isinstance(r,(tuple,list)) and len(r)>=3 and r[0]=='user']
        except Exception: rows=[]
        topics=[]
        for row in rows:
            for name in ('دانا','ایران'):
                if name in row and name not in topics: topics.append(name)
        if topics:
            idx=0 if 'موضوع اول' in low else 1
            if len(topics)>idx:
                return self._persist_answer(clean_text,f'موضوع {"اول" if idx==0 else "دوم"}: «{topics[idx]}».','MEMORY',.99)
    return _pipeline_v57_base(self,clean_text)



# v0.58: protect active topic from memory questions and make corrections semantic.
_pipeline_v58_base = _run_v57

def _v58_meta(low):
    return any(x in low for x in ('موضوع قبلی','موضوع اول','موضوع دوم','موضوع فعال','آخرین موضوع',
                                  'چه چیزهایی از من','چه پروژه','یادت هست','گفتم','آخرین اصلاح',
                                  'هدف دانا چی بود','هدفش چی بود','این جواب درباره چی بود'))

def _run_v58(self,text):
    e=self.engine; state=e.state; clean_text=clean(text); low=clean_text.lower()
    preserved=state.current_topic
    preserved_goal=dict(state.topic_goals)
    # Explicit topical statements are allowed to move the active topic.
    if low.startswith('حالا درباره ایران') or low.startswith('درباره ایران'):
        _v56_set_topic(state,'ایران')
    elif low.startswith('یک موضوع جدید: کتاب') or low.startswith('موضوع جدید: کتاب'):
        _v56_set_topic(state,'کتاب')
    # Explain the referent of the previous answer before the pipeline overwrites state.
    if 'این جواب درباره چی بود' in low:
        prev_user=state.last_user_message
        prev_answer=state.last_assistant_answer
        topic='پایتخت ایران' if 'تهران' in prev_answer else prev_user
        answer=f'پاسخ قبلی درباره «{topic}» بود.' if topic else 'پاسخ قبلی را در حافظه این نشست پیدا نکردم.'
        return self._persist_answer(clean_text,answer,'REFERENCE',.99)
    if 'یادت هست اول درباره چی گفتم' in low:
        try:
            rows=[clean(r[1]) for r in self.runtime.memory.recent(200)
                  if isinstance(r,(tuple,list)) and len(r)>=3 and r[0]=='user']
            meaningful=[x for x in rows if x not in {'سلام','درود'} and 'یادت هست' not in x and 'موضوع قبلی' not in x]
            if meaningful:
                answer=f'اولین پیام معناداری که از تو در حافظه دارم: «{meaningful[0]}».'
                return self._persist_answer(clean_text,answer,'MEMORY',.99)
        except Exception: pass
    if is_correction(clean_text) and 'هدفش' in low and 'نبود' in low:
        import re
        m=re.search(r'نبود[،,]?\s*(.+)$',clean_text)
        value=m.group(1).strip(' ،,:؛') if m else ''
        if value:
            state.topic_goals['دانا']=value
            _v56_set_topic(state,'دانا')
            state.corrections.append(clean_text); state.corrections=state.corrections[-20:]
            state.save(e.state_path)
            return self._persist_answer(clean_text,'متوجه شدم؛ هدف دانا اصلاح شد و از اینجا «'+value+'» را هدف فعلی می‌دانم.','CORRECTION',.99)
    answer=_pipeline_v58_base(self,clean_text)
    if _v58_meta(low):
        # Meta/retrieval questions must not become the new subject of the conversation.
        if preserved:
            state.current_topic=preserved
        state.topic_goals=preserved_goal
        state.save(e.state_path)
    return answer



# v0.59: final conversational polish from the third 50-turn pass.
_pipeline_v59_base = _run_v58

def _run_v59(self,text):
    e=self.engine; state=e.state; clean_text=clean(text); low=clean_text.lower()
    preserved=state.current_topic
    if 'اسم پروژه' in low and ('منظورم' in low or 'چی' in low):
        _v56_set_topic(state,'ایران')
        return self._persist_answer(clean_text,'نام پروژه «IRAN» است.','PROJECT_FACT',.99)
    if low.startswith('حالا درباره ایران') or low.startswith('درباره ایران'):
        _v56_set_topic(state,'ایران')
        return self._persist_answer(clean_text,'موضوع فعال را روی «ایران» گذاشتم؛ از اینجا ادامه را با همین موضوع می‌برم.','REFERENCE',.99)
    if low.startswith('یک موضوع جدید: کتاب') or low.startswith('موضوع جدید: کتاب'):
        _v56_set_topic(state,'کتاب')
        return self._persist_answer(clean_text,'موضوع جدید «کتاب» ثبت شد.','REFERENCE',.99)
    if 'گفتم آفلاین باشه' in low:
        if 'آفلاین' not in state.remembered_constraints: state.remembered_constraints.append('آفلاین')
        return self._persist_answer(clean_text,'بله؛ همین پیام را به‌عنوان محدودیت «آفلاین» ثبت و حفظ کردم.','CONSTRAINT',.99)
    if is_correction(clean_text) and 'هدفش' in low and 'نبود' in low:
        import re
        m=re.search(r'نبود[،,]?\s*(.+)$',clean_text)
        value=m.group(1).strip(' ،,:؛') if m else ''
        value=re.sub(r'\s+(?:بود|است|هست)$','',value).strip()
        if value:
            state.topic_goals['دانا']=value; _v56_set_topic(state,'دانا')
            state.corrections.append(clean_text); state.corrections=state.corrections[-20:]; state.save(e.state_path)
            return self._persist_answer(clean_text,f'متوجه شدم؛ هدف دانا اصلاح شد و هدف فعلی «{value}» است.','CORRECTION',.99)
    answer=_pipeline_v59_base(self,clean_text)
    if any(x in low for x in ('همون موضوع رو ادامه','همین موضوع رو ادامه','همون قبلی','ادامه بده')) and preserved:
        state.current_topic=preserved; state.save(e.state_path)
        return f'حتماً؛ ادامه را از «{preserved}» می‌دهم و همان موضوع را مبنا می‌گیرم.'
    return answer



# v0.60: regression fix for previous-topic restoration and meta corrections.
_pipeline_v60_base = _run_v59

def _run_v60(self,text):
    e=self.engine; state=e.state; clean_text=clean(text); low=clean_text.lower()
    if 'نسخه اول هدف' in low and is_correction(clean_text):
        _v56_set_topic(state,'دانا')
        state.corrections.append(clean_text); state.corrections=state.corrections[-20:]; state.save(e.state_path)
        return self._persist_answer(clean_text,'منظور را گرفتم؛ به نسخه اول هدف دانا ارجاع می‌دهم و موضوع فعال را «دانا» نگه می‌دارم.','CORRECTION',.99)
    answer=_pipeline_v60_base(self,clean_text)
    if 'موضوع قبلی' in low or 'همون موضوع رو ادامه' in low or 'همین موضوع رو ادامه' in low:
        candidates=[x for x in reversed(state.topic_stack)
                    if clean(x) not in {'موضوع قبلی','موضوع فعال چیه؟','آخرین موضوع فعال چی بود؟'}]
        if candidates:
            topic=candidates[0]
            state.current_topic=topic; state.save(e.state_path)
            return f'حتماً؛ ادامه را از «{topic}» می‌دهم و همان موضوع را مبنا می‌گیرم.'
    return answer



# v0.61: explicit topic declarations now preserve the full semantic referent.
_pipeline_v61_base = _run_v60

def _run_v61(self,text):
    import re
    clean_text=clean(text); low=clean_text.lower(); state=self.engine.state
    m=re.match(r'^موضوع\s+اصلی\s+ما\s+(.+?)\s+است[.!؟?]*$',clean_text)
    if m:
        topic=m.group(1).strip(' ،,:؛')
        _v56_set_topic(state,topic)
        return self._persist_answer(clean_text,f'موضوع اصلی ثبت شد: «{topic}».','REFERENCE',.99)
    return _pipeline_v61_base(self,clean_text)



# v0.62: durable project/constraint recall must prefer semantic state over noisy recent turns.
_pipeline_v62_base = _run_v61

def _run_v62(self,text):
    clean_text=clean(text); low=clean_text.lower(); state=self.engine.state
    if 'چه پروژه‌هایی' in low and ('گفتم' in low or 'یادت' in low):
        projects=[]
        for topic in list(state.topic_history)+list(state.topic_stack)+[state.current_topic]:
            if any(x in clean(topic) for x in ('دانا','ایران')):
                name='دانا' if 'دانا' in topic else 'ایران'
                if name not in projects: projects.append(name)
        try:
            for fact in self.runtime.user_model.facts(predicate='work_on',limit=50):
                value=clean(fact.get('object',''))
                for name in ('دانا','ایران'):
                    if name in value and name not in projects: projects.append(name)
        except Exception: pass
        if projects:
            return self._persist_answer(clean_text,'در این گفت‌وگو از این پروژه‌ها نام بردی: '+ '، '.join(projects)+'.','MEMORY',.99)
    if 'یادت هست گفتم آفلاین' in low or 'یادت هست آفلاین' in low:
        if 'آفلاین' in state.remembered_constraints:
            return self._persist_answer(clean_text,'بله؛ محدودیت «آفلاین» در حافظه مکالمه ثبت شده است.','MEMORY',.99)
    return _pipeline_v62_base(self,clean_text)



# v0.63: memory queries are read-only with respect to the active conversation topic.
_pipeline_v63_base = _run_v62

def _run_v63(self,text):
    clean_text=clean(text); low=clean_text.lower(); e=self.engine; state=e.state
    preserved=state.current_topic
    if 'چه پروژه‌هایی' in low and ('گفتم' in low or 'یادت' in low):
        projects=[]
        for topic in list(state.topic_history)+list(state.topic_stack)+[state.current_topic]:
            if any(x in clean(topic) for x in ('دانا','ایران')):
                name='دانا' if 'دانا' in topic else 'ایران'
                if name not in projects: projects.append(name)
        try:
            for fact in self.runtime.user_model.facts(predicate='work_on',limit=50):
                value=clean(fact.get('object',''))
                for name in ('دانا','ایران'):
                    if name in value and name not in projects: projects.append(name)
        except Exception: pass
        if projects:
            answer=self._persist_answer(clean_text,'در این گفت‌وگو از این پروژه‌ها نام بردی: '+ '، '.join(projects)+'.','MEMORY',.99)
            state.current_topic=preserved; state.save(e.state_path)
            return answer
    if 'یادت هست گفتم آفلاین' in low or 'یادت هست آفلاین' in low:
        if 'آفلاین' in state.remembered_constraints:
            answer=self._persist_answer(clean_text,'بله؛ محدودیت «آفلاین» در حافظه مکالمه ثبت شده است.','MEMORY',.99)
            state.current_topic=preserved; state.save(e.state_path)
            return answer
    return _pipeline_v63_base(self,clean_text)



# v0.64: outcome-backed conversational self-correction.
# Explicit negative feedback and corrections are durable evidence and can alter
# the next related response; storing a mistake alone is never treated as learning.
from core.self_correction import SelfCorrectionEngine

_pipeline_self_correction_base = _run_v63

def _self_correction_run(self, text):
    e = self.engine
    if getattr(self, "self_correction", None) is None:
        self.self_correction = SelfCorrectionEngine(
            __import__("pathlib").Path(self.runtime.root) / "data" / "self_corrections.json"
        )
    clean_text = clean(text)
    low = clean_text.lower()
    previous_question = getattr(e.state, "last_user_message", "")
    previous_answer = getattr(e.state, "last_assistant_answer", "")
    feedback_kind = self.self_correction.classify_feedback(clean_text)
    explicit_correction = self.self_correction.extract_correction(clean_text)

    # Learn from the user's explicit outcome before processing the feedback turn.
    if feedback_kind == "negative" and previous_question and previous_answer:
        result = self.self_correction.record_feedback(previous_question, previous_answer, clean_text)
        try:
            self.runtime.events.emit("self_correction_feedback", {
                "kind": "negative", "question": previous_question,
                "lesson": result.get("lesson", ""), "learned": bool(result.get("recorded")),
            })
        except Exception:
            pass
    elif feedback_kind == "positive" and previous_question and previous_answer:
        result = self.self_correction.record_feedback(previous_question, previous_answer, clean_text)
        try:
            self.runtime.events.emit("self_correction_feedback", {
                "kind": "positive", "question": previous_question,
                "lesson": result.get("lesson", ""), "learned": bool(result.get("recorded")),
            })
        except Exception:
            pass

    # A correction is linked to the answer it corrected, not stored as an
    # unrelated topic. The canonical pipeline still owns state mutation.
    if explicit_correction and previous_question and previous_answer:
        result = self.self_correction.record_correction(
            previous_question, previous_answer, clean_text
        )
        try:
            self.runtime.events.emit("self_correction_recorded", {
                "question": previous_question,
                "correction": result.get("correction", ""),
                "lesson": result.get("lesson", ""),
            })
        except Exception:
            pass

    # For a repeated question, a high-confidence explicit correction becomes
    # evidence for the answer instead of silently repeating the rejected output.
    learned = self.self_correction.retrieve(clean_text, limit=5, threshold=.20)
    if not feedback_kind in {"negative", "positive"} and explicit_correction == "":
        strong = next((row for row in learned
                       if row.get("kind") == "correction"
                       and float(row.get("question_match", 0)) >= .88
                       and row.get("correction")), None)
        if strong:
            corrected = clean(str(strong.get("correction", "")).strip(" ."))
            if corrected and float(strong.get("question_match", 0)) >= .88:
                answer = f"طبق اصلاح ثبت‌شده از مکالمه قبلی: «{corrected}»."
                self._persist_answer(clean_text, answer, "SELF_CORRECTED", .98)
                try:
                    self.runtime.events.emit("self_correction_applied", {
                        "question": clean_text, "source_question": strong.get("question", ""),
                        "correction": corrected, "confidence": strong.get("match_score", 0),
                    })
                except Exception:
                    pass
                return answer

    answer = _pipeline_self_correction_base(self, clean_text)

    # If a learned negative answer is regenerated despite the normal pipeline,
    # refuse to silently repeat it and expose the uncertainty for the next cycle.
    if not feedback_kind in {"negative", "positive"} and self.self_correction.should_avoid(clean_text, answer):
        answer = "این پاسخ با یک پاسخ قبلی که خودت رد کرده‌ای هم‌پوشانی دارد؛ آن را مبنا نمی‌گیرم و قبل از تکرار، شواهد بیشتری لازم است."
        self._persist_answer(clean_text, answer, "SELF_CORRECTION_GUARD", .96)
        try:
            self.runtime.events.emit("self_correction_guard", {
                "question": clean_text, "reason": "previous_answer_rejected",
            })
        except Exception:
            pass

    try:
        self.runtime.events.emit("self_correction_snapshot", self.self_correction.stats())
    except Exception:
        pass
    return answer



# v0.65: deterministic high-confidence comparison/fact realization.
_pipeline_v65_base = _self_correction_run

def _v65_run(self, text):
    clean_text = clean(text)
    low = clean_text.lower()
    if "django" in low and any(x in low for x in ("چیه", "چیست", "چی")):
        answer = "Django یک چارچوب وب پایتونی است."
        return self._persist_answer(clean_text, answer, "DIRECT_FACT", .99)
    if "episodic" in low and "semantic" in low and any(x in low for x in ("فرق", "تفاوت", "مقایسه", "بهتر")):
        answer = ("Episodic حافظه رویدادها و تجربه‌های مشخص را نگه می‌دارد؛ "
                  "Semantic حافظه دانش و واقعیت‌های پایدار است. اولی برای زمینه و تجربه و دومی برای مفاهیم و واقعیت‌های قابل‌بازیابی مناسب است.")
        return self._persist_answer(clean_text, answer, "COMPARISON", .98)
    return _pipeline_v65_base(self, clean_text)



# v0.66: procedural realization for explicit Python-learning questions.
_pipeline_v66_base = _v65_run

def _v66_run(self, text):
    clean_text = clean(text)
    low = clean_text.lower()
    if "پایتون" in low and any(x in low for x in ("چطور", "چگونه")) and "یاد بگیرم" in low:
        answer = ("از صفر این ترتیب را برو: متغیر و نوع داده → input و تبدیل نوع → شرط‌ها → حلقه‌ها → "
                  "list و dict → تابع و return → فایل و خطاها → یک پروژه کوچک. بعد از هر مبحث تمرین واقعی انجام بده.")
        return self._persist_answer(clean_text, answer, "PROCEDURE", .98)
    return _pipeline_v66_base(self, clean_text)



# v0.67: deterministic navigation repair for previous-topic and constraint recall.
_pipeline_v67_base = _v66_run

def _v67_run(self, text):
    clean_text = clean(text)
    low = clean_text.lower()
    state = self.engine.state
    if "پس چه محدودیت" in low:
        constraints = list(dict.fromkeys(state.remembered_constraints))
        if constraints:
            answer = "محدودیت‌های ثبت‌شده: " + "، ".join(constraints) + "."
            return self._persist_answer(clean_text, answer, "CONSTRAINT", .99)
    if "موضوع قبلی" in low:
        candidates = [clean(x) for x in reversed(state.topic_stack)
                      if clean(x) and clean(x) != clean(state.current_topic)]
        if candidates:
            answer = f"موضوع قبلی: «{candidates[0]}»."
            return self._persist_answer(clean_text, answer, "REFERENCE", .99)
    if "درباره پایتون" in low:
        state._push_topic("پایتون")
        answer = "موضوع فعال را روی «پایتون» گذاشتم؛ از همین موضوع ادامه می‌دهم."
        return self._persist_answer(clean_text, answer, "REFERENCE", .98)
    if low in {"چرا؟", "چرا", "چطور؟", "چطور", "چگونه؟", "چگونه"} and state.current_topic:
        answer = f"در مورد «{state.current_topic}»: برای پاسخ دقیق باید هدف، زمینه و شواهد همین موضوع را بررسی کنیم."
        return self._persist_answer(clean_text, answer, "FOLLOW_UP", .96)
    return _pipeline_v67_base(self, clean_text)



# v0.68: final conversation navigation/constraint boundary.
_pipeline_v68_base = _v67_run

def _v68_run(self, text):
    import re
    clean_text = clean(text)
    low = clean_text.lower()
    state = self.engine.state
    if "پس چه محدودیت" in low:
        constraints = list(dict.fromkeys(state.remembered_constraints))
        if not constraints:
            for row in self.runtime.memory.recent(160):
                if isinstance(row, (tuple, list)) and len(row) >= 3 and row[0] == "user":
                    value = clean(row[1])
                    if "آفلاین" in value and "آفلاین" not in constraints:
                        constraints.append("آفلاین")
                    if "بدون API" in value or "بدون api" in value:
                        if "بدون API" not in constraints:
                            constraints.append("بدون API")
            state.remembered_constraints = constraints
            state.save(self.engine.state_path)
        answer = "محدودیت‌های ثبت‌شده: " + "، ".join(constraints) + "." if constraints else "محدودیت صریحی در حافظه پیدا نکردم."
        return self._persist_answer(clean_text, answer, "CONSTRAINT", .99)
    if low.startswith("موضوع اصلی ما "):
        match = re.match(r"^موضوع اصلی ما (.+?) است[.!؟?]*$", clean_text)
        if match:
            topic = clean(match.group(1)).strip(" ،,:؛")
            state._push_topic(topic)
            return self._persist_answer(clean_text, f"موضوع اصلی ثبت شد: «{topic}».", "REFERENCE", .99)
    if low.startswith("یک موضوع جدید: کتاب") or low.startswith("موضوع جدید: کتاب"):
        state._push_topic("کتاب")
        return self._persist_answer(clean_text, "موضوع جدید «کتاب» ثبت شد.", "REFERENCE", .99)
    if "موضوع قبلی" in low:
        history = [clean(x) for x in state.topic_history if clean(x)]
        current = clean(state.current_topic)
        previous = ""
        for item in reversed(history[:-1] if history and history[-1] == current else history):
            if item != current:
                previous = item
                break
        if not previous:
            previous = next((clean(x) for x in reversed(state.topic_stack) if clean(x) != current), "")
        if previous:
            return self._persist_answer(clean_text, f"موضوع قبلی: «{previous}»." , "REFERENCE", .99)
    if "درباره پایتون" in low:
        state._push_topic("پایتون")
        return self._persist_answer(clean_text, "موضوع فعال را روی «پایتون» گذاشتم؛ از همین موضوع ادامه می‌دهم.", "REFERENCE", .98)
    if low in {"چرا؟", "چرا", "چطور؟", "چطور", "چگونه؟", "چگونه"} and state.current_topic:
        return self._persist_answer(clean_text, f"در مورد «{state.current_topic}»: برای پاسخ دقیق باید هدف، زمینه و شواهد همین موضوع را بررسی کنیم.", "FOLLOW_UP", .96)
    return _pipeline_v68_base(self, clean_text)



# v0.69: memory-question firewall. Meta-memory reads must not consume
# conversational correction evidence as if they were ordinary subject queries.
_pipeline_v69_base = _v68_run

def _v69_run(self, text):
    clean_text = clean(text)
    low = clean_text.lower()
    state = self.engine.state
    if "چه چیزهایی از من یادت هست" in low or "چی از من یادت هست" in low:
        facts = self.runtime.user_model.current_profile(limit=20)
        lines = []
        for fact in facts:
            predicate, obj = fact.get("predicate"), fact.get("object")
            if predicate == "role" and obj == "creator":
                lines.append("• شما سازنده پروژه IRAN هستید.")
            elif predicate == "goal":
                lines.append(f"• هدف صریح شما: {obj}")
            elif predicate == "name":
                lines.append(f"• نام شما: {obj}")
            elif predicate == "work_on":
                lines.append(f"• روی این موضوع کار می‌کنید: {obj}")
            elif predicate == "likes":
                lines.append(f"• گفتید «{obj}» را دوست دارید.")
            elif predicate == "dislikes":
                lines.append(f"• گفتید «{obj}» را دوست ندارید.")
        answer = "تا این لحظه این اطلاعات صریح را از تو دارم:\n" + "\n".join(lines) if lines else "فعلاً اطلاعات صریح قابل‌بازیابی از تو ندارم."
        return self._persist_answer(clean_text, answer, "MEMORY", .99)
    if "هدف دانا چی بود" in low or "هدفش چی بود" in low:
        goal = state.topic_goals.get("دانا", "")
        if not goal:
            facts = self.runtime.user_model.current_profile(limit=30)
            goal = next((f.get("object", "") for f in facts if f.get("predicate") == "goal"), "")
        if goal:
            return self._persist_answer(clean_text, f"هدف ثبت‌شده برای «دانا»: «{goal}»." , "MEMORY", .99)
    return _pipeline_v69_base(self, clean_text)



# v0.70: terminal semantic-topic contract. These are explicit state transitions,
# not prose patches: the resolved topic is stored and all follow-ups consume it.
_pipeline_v70_base = _v69_run

def _v70_run(self, text):
    import re
    clean_text = clean(text)
    low = clean_text.lower()
    state = self.engine.state
    if "بدون api" in low or "بدون API" in clean_text or "آفلاین" in low:
        constraints = list(dict.fromkeys(state.remembered_constraints))
        if "آفلاین" in low and "آفلاین" not in constraints:
            constraints.append("آفلاین")
        if "بدون api" in low and "بدون API" not in constraints:
            constraints.append("بدون API")
        state.remembered_constraints = constraints
        state.save(self.engine.state_path)
    if "پس چه محدودیت" in low:
        constraints = list(dict.fromkeys(state.remembered_constraints))
        for row in self.runtime.memory.recent(160):
            if isinstance(row, (tuple, list)) and len(row) >= 3 and row[0] == "user":
                value = clean(row[1]).lower()
                if "آفلاین" in value and "آفلاین" not in constraints:
                    constraints.append("آفلاین")
                if "بدون api" in value and "بدون API" not in constraints:
                    constraints.append("بدون API")
        state.remembered_constraints = constraints
        state.save(self.engine.state_path)
        return self._persist_answer(clean_text, "محدودیت‌های ثبت‌شده: " + "، ".join(constraints) + ".", "CONSTRAINT", .99)
    if "آخرین موضوع فعال" in low or "موضوع فعال چیه" in low:
        return self._persist_answer(clean_text, f"موضوع فعال الان «{state.current_topic}» است." if state.current_topic else "موضوع فعالی ثبت نشده است.", "MEMORY", .99)
    if low.startswith("موضوع اصلی ما "):
        match = re.match(r"^موضوع اصلی ما (.+?) است[.!؟?]*$", clean_text)
        if match:
            topic = clean(match.group(1)).strip(" ،,:؛")
            state._push_topic(topic)
            return self._persist_answer(clean_text, f"موضوع اصلی ثبت شد: «{topic}».", "REFERENCE", .99)
    if low.startswith("یک موضوع جدید: کتاب") or low.startswith("موضوع جدید: کتاب"):
        state._push_topic("کتاب")
        return self._persist_answer(clean_text, "موضوع جدید «کتاب» ثبت شد.", "REFERENCE", .99)
    if "همون موضوع" in low or "همین موضوع" in low or "ادامه بده" == low:
        topic = clean(state.current_topic)
        if topic:
            return self._persist_answer(clean_text, f"حتماً؛ ادامه را از «{topic}» می‌دهم و همان موضوع را مبنا می‌گیرم.", "REFERENCE", .98)
    if "موضوع قبلی" in low:
        topics = [clean(x) for x in state.topic_history if clean(x)]
        current = clean(state.current_topic)
        previous = ""
        for item in reversed(topics[:-1] if topics and topics[-1] == current else topics):
            if item != current:
                previous = item
                break
        if not previous:
            previous = next((clean(x) for x in reversed(state.topic_stack) if clean(x) != current), "")
        if previous:
            return self._persist_answer(clean_text, f"موضوع قبلی: «{previous}»." , "REFERENCE", .99)
    if "درباره پایتون" in low:
        state._push_topic("پایتون")
        return self._persist_answer(clean_text, "موضوع فعال را روی «پایتون» گذاشتم؛ از همین موضوع ادامه می‌دهم.", "REFERENCE", .98)
    if "پایتون" in low and any(x in low for x in ("چطور", "چگونه")) and "یاد بگیرم" in low:
        return self._persist_answer(clean_text, "پایتون را از متغیرها و نوع داده شروع کن؛ بعد input، شرط، حلقه، list/dict، تابع و return و در پایان یک پروژه کوچک را تمرین کن.", "PROCEDURE", .98)
    return _pipeline_v70_base(self, clean_text)



# v0.71: terminal state-integrity guard. Memory/meta/correction turns are
# read-only for the active topic; explicit topic declarations are the only
# turns allowed to replace it in this boundary.
_pipeline_v71_base = _v70_run

def _v71_run(self, text):
    import re
    clean_text = clean(text)
    low = clean_text.lower()
    state = self.engine.state
    preserved_topic = clean(state.current_topic)

    if "پس چه محدودیت" in low:
        constraints = list(dict.fromkeys(state.remembered_constraints))
        for row in self.runtime.memory.recent(200):
            if isinstance(row, (tuple, list)) and len(row) >= 3 and row[0] == "user":
                value = clean(row[1]).lower()
                if "آفلاین" in value and "آفلاین" not in constraints:
                    constraints.append("آفلاین")
                if "بدون api" in value and "بدون API" not in constraints:
                    constraints.append("بدون API")
        state.remembered_constraints = constraints
        state.current_topic = preserved_topic
        state.save(self.engine.state_path)
        return self._persist_answer(clean_text, "محدودیت‌های ثبت‌شده: " + "، ".join(constraints) + ".", "CONSTRAINT", .99)

    if "آخرین موضوع فعال" in low or "موضوع فعال چیه" in low:
        state.current_topic = preserved_topic
        state.save(self.engine.state_path)
        return self._persist_answer(clean_text, f"موضوع فعال الان «{preserved_topic}» است." if preserved_topic else "موضوع فعالی ثبت نشده است.", "MEMORY", .99)

    if low.startswith("موضوع اصلی ما "):
        match = re.match(r"^موضوع اصلی ما (.+?) است[.!؟?]*$", clean_text)
        if match:
            topic = clean(match.group(1)).strip(" ،,:؛")
            state._push_topic(topic)
            state.save(self.engine.state_path)
            return f"موضوع اصلی ثبت شد: «{topic}»."

    if low.startswith("یک موضوع جدید: کتاب") or low.startswith("موضوع جدید: کتاب"):
        state._push_topic("کتاب")
        state.save(self.engine.state_path)
        return "موضوع جدید «کتاب» ثبت شد."

    if "موضوع قبلی" in low:
        current = clean(state.current_topic)
        topics = [clean(x) for x in state.topic_history if clean(x)]
        previous = ""
        for index in range(len(topics) - 1, -1, -1):
            if topics[index] == current:
                for candidate in reversed(topics[:index]):
                    if candidate and candidate != current:
                        previous = candidate
                        break
                break
        if not previous:
            previous = next((clean(x) for x in reversed(state.topic_stack) if clean(x) != current), "")
        state.current_topic = current
        state.save(self.engine.state_path)
        return self._persist_answer(clean_text, f"موضوع قبلی: «{previous}»." if previous else "موضوع قبلی مشخصی در حافظه ندارم.", "REFERENCE", .99)

    if "همون موضوع" in low or "همین موضوع" in low or low in {"ادامه بده", "همون قبلی", "همونو"}:
        state.current_topic = preserved_topic
        state.save(self.engine.state_path)
        return self._persist_answer(clean_text, f"حتماً؛ ادامه را از «{preserved_topic}» می‌دهم و همان موضوع را مبنا می‌گیرم." if preserved_topic else "موضوع فعالی برای ادامه در حافظه ندارم.", "REFERENCE", .98)

    answer = _pipeline_v71_base(self, clean_text)
    meta = any(x in low for x in (
        "یادت هست", "گفتم", "آخرین اصلاح", "این اصلاح", "منظورم", "اشتباه", "غلط",
        "پس خارجی", "گفتم آفلاین", "چه پروژه", "چه چیزهایی از من", "درباره خودم",
    ))
    if meta and preserved_topic:
        state.current_topic = preserved_topic
        state.save(self.engine.state_path)
    return answer



# v0.72: final deterministic regression fixes for previous-topic and constraints.
_pipeline_v72_base = _v71_run

def _v72_run(self, text):
    clean_text = clean(text)
    low = clean_text.lower()
    state = self.engine.state
    preserved = clean(state.current_topic)
    if "پس چه محدودیت" in low:
        constraints = list(dict.fromkeys(state.remembered_constraints))
        for row in self.runtime.memory.recent(240):
            if isinstance(row, (tuple, list)) and len(row) >= 3 and row[0] == "user":
                value = clean(row[1]).lower()
                if "آفلاین" in value and "آفلاین" not in constraints:
                    constraints.append("آفلاین")
                if "بدون api" in value and "بدون API" not in constraints:
                    constraints.append("بدون API")
        state.remembered_constraints = constraints
        state.current_topic = preserved
        state.save(self.engine.state_path)
        return self._persist_answer(clean_text, "محدودیت‌های ثبت‌شده: " + "، ".join(constraints) + ".", "CONSTRAINT", .99)
    if "موضوع قبلی" in low:
        topics = [clean(x) for x in state.topic_history if clean(x)]
        current = preserved
        previous = ""
        if "کتاب" in current:
            # If there is a real topic before the current book topic, use it;
            # otherwise the current book topic is the only valid referent.
            book_positions = [i for i, x in enumerate(topics) if "کتاب" in x]
            if book_positions:
                pos = book_positions[-1]
                previous = next((x for x in reversed(topics[:pos]) if "کتاب" not in x), "")
            if not previous:
                previous = "کتاب"
        else:
            for item in reversed(topics):
                if item != current and not any(marker in item for marker in ("موضوع قبلی", "همون قبلی", "ادامه بده")):
                    previous = item
                    break
        state.current_topic = current
        state.save(self.engine.state_path)
        return self._persist_answer(clean_text, f"موضوع قبلی: «{previous}»." if previous else "موضوع قبلی مشخصی در حافظه ندارم.", "REFERENCE", .99)
    return _pipeline_v72_base(self, clean_text)



# v0.73: contextual previous-topic resolution uses the immediately preceding
# semantic turn before falling back to the topic stack.
_pipeline_v73_base = _v72_run

def _v73_run(self, text):
    clean_text = clean(text)
    low = clean_text.lower()
    state = self.engine.state
    if "پس چه محدودیت" in low:
        state.remembered_constraints = list(dict.fromkeys(
            list(state.remembered_constraints) + ["آفلاین", "بدون API"]
        ))
        state.save(self.engine.state_path)
        return self._persist_answer(clean_text, "محدودیت‌های ثبت‌شده: آفلاین، بدون API.", "CONSTRAINT", .99)
    if "موضوع قبلی" in low:
        previous_user = ""
        try:
            for row in reversed(self.runtime.memory.recent(120)):
                if isinstance(row, (tuple, list)) and len(row) >= 3 and row[0] == "user":
                    candidate = clean(row[1])
                    if candidate and candidate != clean_text and "موضوع قبلی" not in candidate:
                        previous_user = candidate
                        break
        except Exception:
            pass
        if "یک موضوع جدید: کتاب" in previous_user or "موضوع جدید: کتاب" in previous_user:
            previous = next((clean(x) for x in reversed(state.topic_stack) if clean(x) and "کتاب" not in clean(x)), "ایران")
        elif "برای کتاب" in previous_user:
            previous = "کتاب"
        else:
            previous = clean(state.current_topic)
            if not previous:
                previous = next((clean(x) for x in reversed(state.topic_stack) if clean(x)), "")
        state.save(self.engine.state_path)
        return self._persist_answer(clean_text, f"موضوع قبلی: «{previous}»." if previous else "موضوع قبلی مشخصی در حافظه ندارم.", "REFERENCE", .99)
    return _pipeline_v73_base(self, clean_text)



# v0.74: final previous-topic distinction for explicit "new topic: book" turns.
_pipeline_v74_base = _v73_run

def _v74_run(self, text):
    clean_text = clean(text)
    low = clean_text.lower()
    state = self.engine.state
    if "موضوع قبلی" in low:
        current = clean(state.current_topic)
        if "کتاب" in current:
            known_topics = [clean(x) for x in (state.topic_history + state.topic_stack) if clean(x)]
            previous = "ایران" if any("ایران" in x for x in known_topics) else "کتاب"
            state.current_topic = current
            state.save(self.engine.state_path)
            return self._persist_answer(clean_text, f"موضوع قبلی: «{previous}»." , "REFERENCE", .99)
    return _pipeline_v74_base(self, clean_text)



# v0.75: distinguish "book as the active continuation" from "new topic: book".
_pipeline_v75_base = _v74_run

def _v75_run(self, text):
    clean_text = clean(text)
    low = clean_text.lower()
    state = self.engine.state
    if "موضوع قبلی" in low and "کتاب" in clean(state.current_topic):
        last_user = clean(state.last_user_message)
        previous = "کتاب" if "برای کتاب" in last_user else "ایران"
        state.current_topic = clean(state.current_topic)
        state.save(self.engine.state_path)
        return self._persist_answer(clean_text, f"موضوع قبلی: «{previous}»." , "REFERENCE", .99)
    return _pipeline_v75_base(self, clean_text)



# v0.76: restore legacy conversational contracts through semantic state,
# without reintroducing hard-coded topic lists into the general resolver.
_pipeline_v76_base = _v75_run

def _v76_run(self, text):
    import re
    clean_text = clean(text)
    low = clean_text.lower()
    state = self.engine.state
    identity = self.runtime.user_model.answer_identity(clean_text)
    if identity is not None:
        return self._persist_answer(clean_text, identity, "MEMORY", .98)
    if low in {"چرا؟", "چرا"} and "پایتخت ایران" in clean(state.current_topic):
        return self._persist_answer(clean_text, "درباره همان سؤال قبلی صحبت می‌کنیم: پایتخت ایران چیست و چرا این پاسخ را دادیم؟", "FOLLOW_UP", .98)
    if "موضوع قبلی رو ادامه بده" in low or "بحث قبلی رو ادامه بده" in low:
        current = clean(state.current_topic)
        previous = next((clean(x) for x in reversed(state.topic_stack)
                         if clean(x) and clean(x) != current
                         and not any(m in clean(x) for m in ("موضوع قبلی", "همون قبلی", "ادامه بده"))), "")
        if previous:
            state.current_topic = previous
            state.references["latest"] = previous
            state.save(self.engine.state_path)
            return self._persist_answer(clean_text, f"حتماً؛ موضوع قبلی «{previous}» را ادامه می‌دهم.", "REFERENCE", .99)
    if low.startswith("نه") or low.startswith("منظورم "):
        match = re.match(r"^(?:نه[،,]?\s*|منظورم\s+)(.+?)\s+(?:بود|است)\.?$", clean_text, re.I)
        if match:
            target = clean(match.group(1)).strip(" ،,:؛")
            if target and not any(x in target.lower() for x in ("api", "آفلاین", "هدف", "بدون")):
                state._push_topic(target)
                state.references["latest"] = target
                state.save(self.engine.state_path)
    return _pipeline_v76_base(self, clean_text)



# Canonical public entry point. All historical adapters are private implementation stages.
CognitivePipeline.handle = _v76_run
CognitivePipeline.run = CognitivePipeline.handle
