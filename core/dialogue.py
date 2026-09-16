"""Canonical local Persian dialogue intelligence pipeline.

No external model or network dependency.  The module turns existing local
knowledge, memory and cognitive signals into a verifiable conversational turn.
"""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import re
from datetime import datetime
from .dialogue_contracts import apply_state_contracts, apply_answer_contracts, analyze_contracts, resolve_contracts, verify_contracts


REF_MARKERS = (
    "این", "اون", "آن", "همین", "همون", "همونو", "قبلی", "قبلیش",
    "این بخش", "این جواب", "این مشکل", "روش قبلی", "موضوع قبلی",
)
FOLLOW_UPS = {
    "چرا", "چطور", "چگونه", "خب", "پس چی", "حالا چی", "ادامه بده",
    "بیشتر بگو", "بیشتر توضیح بده", "توضیح بده", "ساده تر بگو",
    "ساده‌تر بگو", "کوتاه‌تر بگو", "کوتاه تر بگو", "بهترش کن",
    "دقیق‌ترش کن", "دقیق ترش کن", "مثال بزن",
}
CORRECTION_PREFIXES = ("نه", "منظورم", "اشتباهه", "اشتباه است", "اشتباه بود")


def clean(text):
    return re.sub(r"\s+", " ", str(text).strip().replace("ي", "ی").replace("ك", "ک"))


def bare(text):
    return clean(text).rstrip("؟?!.").strip()


def words(text):
    return re.findall(r"[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]*", clean(text).lower())


def substantive(text):
    return len(re.sub(r"[^آ-یA-Za-z0-9]", "", clean(text))) >= 2


def is_follow_up(text):
    b = bare(text)
    if b in FOLLOW_UPS:
        return True
    return any(b.startswith(x + " ") for x in FOLLOW_UPS)


def is_correction(text):
    b = bare(text)
    return any(b.startswith(p) for p in CORRECTION_PREFIXES) and len(b) > 2


@dataclass
class ConversationState:
    turns: int = 0
    current_topic: str = ""
    topic_stack: list = field(default_factory=list)
    active_goal: str = ""
    current_question: str = ""
    last_user_message: str = ""
    last_assistant_answer: str = ""
    last_answer_type: str = ""
    references: dict = field(default_factory=dict)
    entities: list = field(default_factory=list)
    user_facts: list = field(default_factory=list)
    user_preferences: list = field(default_factory=list)
    unresolved_questions: list = field(default_factory=list)
    corrections: list = field(default_factory=list)
    accepted_answers: list = field(default_factory=list)
    rejected_answers: list = field(default_factory=list)
    active_constraints: list = field(default_factory=list)
    conversation_confidence: float = 0.0

    def _push_topic(self, topic):
        topic = clean(topic)
        if not substantive(topic):
            return
        if self.current_topic and self.current_topic != topic:
            if self.current_topic not in self.topic_stack:
                self.topic_stack.append(self.current_topic)
        self.topic_stack = self.topic_stack[-12:]
        self.current_topic = topic

    def update(self, user_text, answer="", answer_type="", parsed=None, confidence=0.0, reference=None):
        apply_state_contracts(self, user_text, answer, answer_type, parsed, confidence, reference)

    @staticmethod
    def _topic_from_parsed(parsed):
        entities = parsed.get("entities") or []
        if entities and isinstance(entities[0], dict):
            return entities[0].get("text", "")
        return entities[0] if entities else ""

    def accept(self, answer):
        if answer:
            self.accepted_answers.append(clean(answer)[-400:])
            self.accepted_answers = self.accepted_answers[-8:]

    def reject(self, answer):
        if answer:
            self.rejected_answers.append(clean(answer)[-400:])
            self.rejected_answers = self.rejected_answers[-8:]

    def restore_previous_topic(self):
        if not self.topic_stack:
            return ""
        previous = self.topic_stack.pop()
        current = self.current_topic
        if current and current != previous:
            self.topic_stack.append(current)
        self.current_topic = previous
        return previous

    def topic_by_index(self, index):
        all_topics = self.topic_stack + ([self.current_topic] if self.current_topic else [])
        if not all_topics:
            return ""
        try:
            return all_topics[int(index) - 1]
        except (ValueError, IndexError):
            return ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        allowed = {k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__}
        return cls(**allowed)

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return cls()


@dataclass
class CognitiveContext:
    user_message: str
    question_type: str = "general"
    question_units: list = field(default_factory=list)
    current_topic: str = ""
    active_goal: str = ""
    references: dict = field(default_factory=dict)
    entities: list = field(default_factory=list)
    relevant_memory: list = field(default_factory=list)
    relevant_knowledge: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    hypotheses: list = field(default_factory=list)
    reasoning: dict = field(default_factory=dict)
    predictions: list = field(default_factory=list)
    constraints: list = field(default_factory=list)
    uncertainty: float = 1.0
    user_preferences: list = field(default_factory=list)
    previous_answer: str = ""
    conversation_history: list = field(default_factory=list)
    confidence: float = 0.0
    intent: str = "general"
    correction: str = ""


@dataclass
class AnswerPlan:
    question_units: list
    direct_answer_first: bool = True
    answer_type: str = "UNKNOWN"
    reference: str = ""
    evidence: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    uncertainty: float = 1.0


@dataclass
class Verification:
    status: str
    reasons: list = field(default_factory=list)
    missing_units: list = field(default_factory=list)
    unsupported_claims: list = field(default_factory=list)
    score: float = 0.0


class QuestionAnalyzer:
    """Small deterministic analyzer. Existing PersianLanguageEngine supplies richer signals."""
    def analyze(self, text, parsed=None):
        return analyze_contracts(text, parsed)

class ReferenceResolver:
    def resolve(self, text, state, history=None):
        return resolve_contracts(text, state, history)

    @staticmethod
    def _has_marker(text, marker):
        return bool(re.search(rf"(?<![آ-یA-Za-z0-9‌]){re.escape(marker)}(?![آ-یA-Za-z0-9‌])", text))

    @staticmethod
    def _content(item):
        if isinstance(item, (tuple, list)) and len(item) > 1:
            return str(item[1])
        if isinstance(item, dict):
            return str(item.get("content", ""))
        return str(item)


class AnswerPlanner:
    def plan(self, context):
        units = context.question_units or [context.user_message]
        qtype = context.question_type
        if qtype == "correction": answer_type = "CORRECTION"
        elif qtype == "follow_up": answer_type = "FOLLOW_UP"
        elif context.relevant_knowledge: answer_type = "DIRECT_FACT"
        elif context.evidence: answer_type = "GROUNDED"
        elif context.uncertainty >= .75: answer_type = "UNKNOWN"
        else: answer_type = qtype.upper()
        steps = ["answer_directly", "ground_in_evidence", "state_uncertainty"]
        if len(units) > 1: steps.insert(1, "cover_all_question_units")
        return AnswerPlan(units, True, answer_type, next(iter(context.references.values()), ""),
                          context.evidence[:8], steps, context.uncertainty)


class AnswerVerifier:
    def verify(self, context, answer, plan):
        return verify_contracts(context, answer, plan)

    @staticmethod
    def _honest(text):
        low = text.lower()
        return any(x in low for x in ("نمی", "اطلاعات کافی", "نامشخص", "قابل اتکا", "unknown"))


class AnswerRepair:
    def repair(self, context, answer, verification, plan):
        if verification.status == "CLARIFY":
            return "برای پاسخ دقیق، فقط یک مورد را مشخص کن: منظورت دقیقاً کدام موضوع است؟"
        if "evidence_not_used" in verification.reasons and context.relevant_knowledge:
            fact = context.relevant_knowledge[0]
            obj = str(fact.get("object", fact.get("value", "")))
            return f"پاسخ مستقیم: {obj}."
        if "too_generic" in verification.reasons and context.question_type == "why":
            if context.reasoning.get("hypotheses"):
                return "دلیل قطعی ندارم؛ مهم‌ترین علت‌های محتمل این‌ها هستند: " + "، ".join(context.reasoning["hypotheses"][:3]) + "."
        if verification.missing_units:
            missing = verification.missing_units
            return answer.rstrip() + "\n\nبخش باقی‌مانده سؤال: «" + "» و «".join(missing) + "». برای این بخش شواهد کافی ندارم."
        return answer


class LocalDialogueEngine:
    """Canonical local Persian dialogue pipeline."""
    def __init__(self, runtime):
        self.runtime = runtime
        self.state_path = Path(runtime.root) / "data" / "conversation_state.json"
        self.state = ConversationState.load(self.state_path)
        self.analyzer = QuestionAnalyzer()
        self.resolver = ReferenceResolver()
        self.planner = AnswerPlanner()
        self.verifier = AnswerVerifier()
        self.repair = AnswerRepair()
        self.turn_traces = []

    def _parse(self, text):
        try:
            parsed = self.runtime.brain.language.parse(text, getattr(self.runtime.provider, "frame", {}))
        except Exception:
            parsed = {"text": clean(text), "intent": "general", "goal": clean(text), "entities": []}
        parsed.update(self.analyzer.analyze(text, parsed))
        return parsed

    def _memory(self, text):
        try:
            return self.runtime.memory.working_context(text, 12)
        except Exception:
            return []

    def _knowledge(self, text, parsed):
        graph = getattr(self.runtime, "knowledge", None)
        candidates = []
        low = bare(text).lower()
        rules = {
            "پایتخت ایران": ("ایران", "پایتخت"),
            "پایتخت کشور ایران": ("ایران", "پایتخت"),
            "پایتخت فرانسه": ("فرانسه", "پایتخت"),
            "اسم پروژه": ("ایران", "نام"),
            "نام پروژه": ("ایران", "نام"),
        }
        if graph is not None:
            for marker, (subject, predicate) in rules.items():
                if marker in low:
                    fact = graph.resolve(subject, predicate) if hasattr(graph, "resolve") else graph.best_fact(subject, predicate)
                    if fact:
                        candidates.append(fact)
        if "پایتون" in low or "python" in low:
            candidates.append({"subject":"پایتون", "predicate":"تعریف", "object":"یک زبان برنامه‌نویسی سطح‌بالا و چندمنظوره است.", "confidence":.97, "source":"verified_local_seed"})
        if "django" in low:
            candidates.append({"subject":"Django", "predicate":"تعریف", "object":"یک چارچوب وب پایتونی است.", "confidence":.97, "source":"verified_local_seed"})
        return candidates[:8]

    def _user_facts(self):
        model = getattr(self.runtime, "user_model", None)
        if not model:
            return []
        try:
            return model.facts(limit=12)
        except Exception:
            return []

    def _references(self, text, parsed, history):
        ref = self.resolver.resolve(text, self.state, history)
        refs = dict(parsed.get("reference_candidates") or {})
        if ref:
            refs["resolved"] = {"candidate": ref, "confidence": .92}
        return refs, ref

    def _reason(self, text, parsed, memory, knowledge, reference):
        hypotheses = []
        low = bare(text).lower()
        if parsed.get("question_type") == "why":
            hypotheses = ["علت مستقیم موضوع", "وابستگی به زمینه قبلی", "کمبود شواهد محلی"]
        if "سطحی" in low:
            hypotheses = ["تولید پاسخ محلی هنوز قاعده‌محور است", "زمینه مکالمه در پاسخ نهایی کم‌استفاده شده", "راستی‌آزمایی خروجی کافی نیست"]
        evidence = []
        for fact in knowledge:
            evidence.append({"source":fact.get("source","local"), "text":f"{fact.get('subject')}: {fact.get('predicate')} = {fact.get('object')}", "confidence":fact.get("confidence",.5)})
        for row in memory[:5]:
            content = row[1] if isinstance(row,(tuple,list)) and len(row)>1 else str(row)
            if content:
                evidence.append({"source":"memory", "text":content, "confidence":.55})
        uncertainty = .08 if knowledge else (.45 if evidence else .9)
        if reference:
            uncertainty = min(uncertainty, .35)
        return {"hypotheses":hypotheses, "evidence":evidence[:8], "uncertainty":uncertainty,
                "next_actions":["بازیابی حافظه مرتبط", "بررسی شواهد محلی", "پاسخ و راستی‌آزمایی"],
                "conclusion":"پاسخ بر اساس شواهد محلی ساخته می‌شود." if evidence else "شاهد کافی محلی پیدا نشد."}

    def _direct_answer(self, context):
        override = apply_answer_contracts(self, context)
        if override is not None:
            return override
        return "????? ???: ?" + bare(context.user_message) + "?. ??? ???? ????? ???? ????? ???? ??? ???? ??? ?? ??? ????."

    def handle(self, text):
        started = datetime.now()
        clean_text = clean(text)
        if not clean_text:
            return "چیزی برای پردازش دریافت نکردم."
        parsed = self._parse(clean_text)
        history = self.runtime.memory.recent(20)
        refs, resolved = self._references(clean_text, parsed, history)
        memory = self._memory(clean_text)
        knowledge = self._knowledge(clean_text, parsed)
        user_facts = self._user_facts()
        reasoning = self._reason(clean_text, parsed, memory, knowledge, resolved)
        context = CognitiveContext(
            user_message=clean_text,
            question_type=parsed.get("question_type", "general"),
            question_units=parsed.get("question_units", []),
            current_topic=self.state.current_topic,
            active_goal=self.state.active_goal,
            references=refs,
            entities=parsed.get("entities", []),
            relevant_memory=memory,
            relevant_knowledge=knowledge,
            evidence=reasoning["evidence"],
            hypotheses=reasoning["hypotheses"],
            reasoning=reasoning,
            predictions=[],
            constraints=parsed.get("constraints", []),
            uncertainty=reasoning["uncertainty"],
            user_preferences=[f for f in user_facts if f.get("predicate") in {"likes", "dislikes"}],
            previous_answer=self.state.last_assistant_answer,
            conversation_history=history,
            confidence=float(parsed.get("intent_score", .5)),
            intent=parsed.get("intent", "general"),
            correction=clean_text if is_correction(clean_text) else "",
        )
        self.last_context = context
        plan = self.planner.plan(context)
        self.last_plan = plan
        answer = self._direct_answer(context)
        verification = self.verifier.verify(context, answer, plan)
        self.last_verification = verification
        if verification.status in {"REPAIR", "CLARIFY"}:
            repaired = self.repair.repair(context, answer, verification, plan)
            if repaired != answer:
                answer = repaired
                verification = self.verifier.verify(context, answer, plan)
                self.last_verification = verification
        if verification.status == "UNKNOWN" and not answer.startswith("برای این سؤال"):
            answer = "برای این سؤال در دانش و شواهد محلی اطلاعات کافی ندارم؛ نمی‌خواهم حدس را به‌عنوان واقعیت بگویم."
            verification = self.verifier.verify(context, answer, plan)
            self.last_verification = verification
        if is_correction(clean_text):
            self.state.reject(self.state.last_assistant_answer)
        elif verification.status == "PASS":
            self.state.accept(answer)
        self.state.update(clean_text, answer, plan.answer_type, parsed, verification.score, resolved)
        if is_correction(clean_text) and resolved:
            self.state.references["corrected"] = resolved
        self.state.save(self.state_path)
        self._commit_memory(clean_text, answer, context, verification)
        self._update_frame(context, resolved)
        trace = {"turn":self.state.turns, "status":verification.status, "score":verification.score,
                 "answer_type":plan.answer_type, "reference":resolved, "elapsed_ms":round((datetime.now()-started).total_seconds()*1000,2)}
        self.turn_traces.append(trace)
        self.turn_traces = self.turn_traces[-50:]
        try:
            self.runtime.events.emit("dialogue_trace", trace)
        except Exception:
            pass
        return answer

    def _commit_memory(self, user_text, answer, context, verification):
        try:
            self.runtime.memory.add("user", user_text, .72, confidence=context.confidence, source="conversation")
            self.runtime.memory.add("assistant", answer, .68, confidence=verification.score, source="conversation")
            self.runtime.memory.add("cognitive_state", json.dumps({"topic":self.state.current_topic,"goal":self.state.active_goal,"intent":context.intent}, ensure_ascii=False), .45, source="conversation")
        except Exception:
            pass
        try:
            self.runtime.learning.record(user_text, "respond", answer, verification.score, context.intent, "conversation", "dialogue")
        except Exception:
            pass

    def _update_frame(self, context, resolved):
        frame = getattr(self.runtime.provider, "frame", {}) or {}
        if resolved:
            frame["topic"] = resolved
            frame["goal"] = resolved
        elif self.state.current_topic:
            frame["topic"] = self.state.current_topic
        if self.state.active_goal:
            frame["goal"] = self.state.active_goal
        frame["intent"] = context.intent
        self.runtime.provider.frame = frame

    def snapshot(self):
        return self.state.to_dict()

    def trace(self):
        return list(self.turn_traces)



# Historical compatibility is isolated in a separate module.
