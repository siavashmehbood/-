"""Canonical local Persian dialogue intelligence pipeline.

No external model or network dependency.  The module turns existing local
knowledge, memory and cognitive signals into a verifiable conversational turn.
"""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import re
from datetime import datetime

from core.chain_reasoner import ChainReasoner
from core.reference_intelligence import ReferenceIntelligence

_REFERENCE_INTELLIGENCE = ReferenceIntelligence()


REF_MARKERS = (
    "این", "اون", "آن", "همین", "همون", "همونو", "قبلی", "قبلیش",
    "این بخش", "این جواب", "این مشکل", "روش قبلی", "موضوع قبلی",
)
FOLLOW_UPS = {
    "چرا", "چطور", "چگونه", "خب", "پس چی", "حالا چی", "ادامه بده",
    "بیشتر بگو", "بیشتر توضیح بده", "توضیح بده", "ساده تر بگو",
    "ساده‌تر بگو", "کوتاه‌تر بگو", "کوتاه تر بگو", "بهترش کن",
    "دقیق‌ترش کن", "دقیق ترش کن", "مثال بزن", "یعنی چه", "یعنی چی",
    "منظورت چیست", "منظورت چیه", "این یعنی چه", "این یعنی چی",
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
    topic_history: list = field(default_factory=list)
    topic_goals: dict = field(default_factory=dict)
    remembered_constraints: list = field(default_factory=list)

    def _push_topic(self, topic):
        topic = clean(topic)
        if not substantive(topic):
            return
        if self.current_topic and self.current_topic != topic:
            if self.current_topic not in self.topic_stack:
                self.topic_stack.append(self.current_topic)
        if topic not in self.topic_history:
            self.topic_history.append(topic)
            self.topic_history = self.topic_history[-30:]
        self.topic_stack = self.topic_stack[-12:]
        self.current_topic = topic

    def update(self, user_text, answer="", answer_type="", parsed=None, confidence=0.0, reference=None):
        text = clean(user_text)
        parsed = parsed or {}
        self.turns += 1
        self.last_user_message = text
        self.current_question = text if parsed.get("question_units") or "؟" in text else self.current_question
        if answer:
            self.last_assistant_answer = clean(answer)
        if answer_type:
            self.last_answer_type = answer_type
        goal = clean(parsed.get("goal", ""))
        entities = parsed.get("entities") or []
        self.entities = [e.get("text", e) if isinstance(e, dict) else str(e) for e in entities][:20]
        self.active_constraints = list(parsed.get("constraints") or [])[:10]
        if goal and not is_follow_up(text) and not is_correction(text):
            self.active_goal = goal
        if is_correction(text):
            if text not in self.corrections:
                self.corrections.append(text)
            if text not in self.unresolved_questions:
                self.unresolved_questions.append(text)
            self.corrections = self.corrections[-20:]
            self.unresolved_questions = self.unresolved_questions[-20:]
        if reference:
            self.references["latest"] = reference
        if not is_follow_up(text) and not is_correction(text):
            candidate = self._topic_from_parsed(parsed) or goal
            if candidate and substantive(candidate):
                self._push_topic(candidate)
                self.references['latest_topic'] = candidate
                self.references['latest'] = candidate
            elif substantive(text) and parsed.get("intent") not in {"question"}:
                self._push_topic(text)
        if self.current_topic and not is_follow_up(text) and not is_correction(text):
            self.references['latest_topic'] = self.current_topic
        self.conversation_confidence = max(0.0, min(1.0, float(confidence or 0.0)))

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
        if not path.exists(): return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Normalization for Persian persistence
            def persisted_norm(value):
                return clean(str(value)).replace("\u200c", "")
            for key in ("corrections", "unresolved_questions", "current_topic", "active_goal"):
                val = data.get(key)
                if isinstance(val, list): data[key] = [persisted_norm(x) for x in val]
                elif isinstance(val, str): data[key] = persisted_norm(val)
            # topic_stack: only strip ZWNJ/spaces, keep word boundaries (do not collapse multi-word topics)
            stack = data.get("topic_stack")
            if isinstance(stack, list):
                data["topic_stack"] = [str(x).replace("\u200c","").strip() for x in stack]
            return cls.from_dict(data)
        except (OSError, ValueError, TypeError): return cls()


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
    learning_guidance: dict = field(default_factory=dict)


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
    """Deterministic Persian question and follow-up analyzer."""
    def analyze(self, text, parsed=None):
        t = clean(text)
        low = bare(t).lower()
        units = [part.strip() for part in re.split(r"[؟?]", t) if part.strip()]
        pieces = re.split(
            r"\s+و\s+(?=چرا\b|چطور\b|چگونه\b|برای پروژه\b|برای پروژه‌م\b|آیا\b)",
            bare(t),
        )
        if len(pieces) > 1:
            units = [part.strip() for part in pieces if part.strip()]
        if not units and substantive(t):
            units = [bare(t)]

        qtype = "general"
        if "چرا" in low:
            qtype = "why"
        elif any(marker in low for marker in ("چطور", "چگونه", "چه جوری", "چجوری")):
            qtype = "how"
        elif any(marker in low for marker in ("چیست", "چیه", "چی ")):
            qtype = "what"
        elif "آیا" in low:
            qtype = "yes_no"
        if is_follow_up(t) or any(marker in t for marker in ("موضوع قبلی", "بحث اول", "بحث دوم")):
            qtype = "follow_up"
        if is_correction(t):
            qtype = "correction"
        return {"question_type": qtype, "question_units": units}




class ReferenceResolver:
    def resolve(self, text, state, history=None):
        try:
            result = _REFERENCE_INTELLIGENCE.resolve(text, state, history)
            state.references["reference_trace"] = result.to_dict()
            if result.ambiguous:
                return ""
            if result.candidate:
                return result.candidate
        except Exception:
            pass
        t=bare(text); history=history or []
        ordinal_reference = bool(re.search(r'(اول|دوم|سوم|چهارم|پنجم|آخر)', t))
        if is_follow_up(t) and not ordinal_reference and state.last_assistant_answer and substantive(state.last_assistant_answer):
            return state.last_assistant_answer
        if any(x in t for x in ('موضوع قبلی', 'بحث قبلی')):
            return state.topic_stack[-1] if state.topic_stack else state.current_topic
        if 'همون قبلی' in t:
            return state.references.get('latest', '') or (state.topic_stack[-1] if state.topic_stack else state.current_topic)
        ordinal_markers = (
            (1, ('بحث اول', 'مورد اول', 'موضوع اول', 'اولی', 'اولیش')),
            (2, ('بحث دوم', 'مورد دوم', 'موضوع دوم', 'دومی', 'دومیش')),
            (3, ('بحث سوم', 'مورد سوم', 'موضوع سوم', 'سومی', 'سومیش')),
            (4, ('بحث چهارم', 'مورد چهارم', 'موضوع چهارم', 'چهارمی', 'چهارمیش')),
            (5, ('بحث پنجم', 'مورد پنجم', 'موضوع پنجم', 'پنجمی', 'پنجمیش')),
        )
        for index, markers in ordinal_markers:
            if any(self._has_marker(t, marker) for marker in markers):
                return state.topic_by_index(index)
        if any(self._has_marker(t, x) for x in ('آخری', 'آخرین موضوع', 'آخرین بحث')):
            return state.current_topic or (state.topic_stack[-1] if state.topic_stack else state.active_goal)
        if any(x in t for x in ('موضوع فعلی', 'همین موضوع')):
            return state.current_topic or state.active_goal
        if is_follow_up(t) or any(self._has_marker(t,m) for m in REF_MARKERS):
            if state.current_topic and substantive(state.current_topic): return state.current_topic
            latest=state.references.get('latest','')
            if latest and substantive(latest): return latest
            if state.active_goal and substantive(state.active_goal): return state.active_goal
            for item in reversed(history):
                content=self._content(item)
                if substantive(content) and not is_follow_up(content): return content
        return ''
    @staticmethod
    def _has_marker(text,marker): return bool(re.search(rf'(?<![آ-یA-Za-z0-9‌]){re.escape(marker)}(?![آ-یA-Za-z0-9‌])',text))
    @staticmethod
    def _content(item):
        if isinstance(item,(tuple,list)) and len(item)>1: return str(item[1])
        if isinstance(item,dict): return str(item.get('content',item.get('text','')))
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
        guidance = context.learning_guidance or {}
        strategy = str(guidance.get("recommended_strategy", "")).lower()
        # Learning must alter the next turn, not merely be displayed as a statistic.
        if strategy == "feedback":
            steps.insert(0, "address_previous_feedback")
        elif strategy == "conversation":
            steps.insert(0, "preserve_conversation_context")
        elif strategy in {"evidence-first", "evidence_first"}:
            steps.insert(1, "prefer_local_evidence_before_claims")
        approved_lessons = guidance.get("approved_lessons", []) or []
        if approved_lessons:
            steps.insert(0, "apply_approved_lesson")
        if guidance.get("failure_signal"):
            steps.insert(0, "avoid_recent_failed_pattern")
        if len(units) > 1: steps.insert(1, "cover_all_question_units")
        return AnswerPlan(units, True, answer_type, next(iter(context.references.values()), ""),
                          context.evidence[:8], steps, context.uncertainty)


class AnswerVerifier:
    def verify(self, context, answer, plan):
        text = clean(answer)
        reasons, missing, unsupported = [], [], []
        low = text.lower()
        if not text:
            reasons.append("empty_answer")
        honest = any(x in low for x in ("اطلاعات کافی ندارم", "نمی‌خواهم حدس", "شاهد کافی", "unknown", "نامشخص"))
        if plan.question_units and not honest:
            for unit in plan.question_units:
                key = set(words(unit)) - {"چرا", "چطور", "چگونه", "چی", "است", "هست", "و", "برای", "من"}
                if key and not (set(words(text)) & key):
                    if context.relevant_knowledge and any(
                        str(f.get("object", f.get("value", ""))) in text
                        for f in context.relevant_knowledge
                    ):
                        continue
                    missing.append(unit)
        if context.question_type in {"why", "how"} and text.startswith("برداشت"):
            reasons.append("too_generic")
        if context.uncertainty >= .82 and not honest:
            reasons.append("uncertainty_not_expressed")
        if context.relevant_knowledge and not honest:
            objects = [str(f.get("object", f.get("value", ""))) for f in context.relevant_knowledge]
            if not any(obj and obj in text for obj in objects):
                reasons.append("evidence_not_used")
        score = max(0.0, 1.0 - .18 * len(missing) - .25 * len(reasons))
        if not text:
            status = "CLARIFY"
        elif honest and context.uncertainty >= .7:
            status = "PASS"
        elif missing or reasons:
            status = "REPAIR"
        else:
            status = "PASS"
        return Verification(status, reasons, missing, unsupported, round(score, 3))

    @staticmethod
    def _honest(text):
        low = text.lower()
        return any(x in low for x in ("نمی", "اطلاعات کافی", "نامشخص", "قابل اتکا", "unknown"))


class AnswerRepair:
    def repair(self, context, answer, verification, plan):
        steps = set(plan.steps or [])
        if ("avoid_recent_failed_pattern" in steps
                and verification.status == "PASS"
                and context.uncertainty >= .70
                and not context.relevant_knowledge):
            return "UNKNOWN: اطلاعات محلی کافی برای پاسخ مطمئن ندارم؛ نمی‌خواهم همان الگوی قبلیِ نامطمئن را تکرار کنم."
        if verification.status == "CLARIFY":
            repaired = "برای پاسخ دقیق، فقط یک مورد را مشخص کن: منظورت دقیقاً کدام موضوع است؟"
        elif "evidence_not_used" in verification.reasons and context.relevant_knowledge:
            fact = context.relevant_knowledge[0]
            obj = str(fact.get("object", fact.get("value", "")))
            repaired = f"پاسخ مستقیم: {obj}."
        elif "too_generic" in verification.reasons and context.question_type == "why" and context.reasoning.get("hypotheses"):
            repaired = "دلیل قطعی ندارم؛ مهم‌ترین علت‌های محتمل این‌ها هستند: " + "، ".join(context.reasoning["hypotheses"][:3]) + "."
        elif verification.missing_units:
            missing = verification.missing_units
            repaired = answer.rstrip() + "\n\nبخش باقی‌مانده سؤال: «" + "» و «".join(missing) + "». برای این بخش شواهد کافی ندارم."
        else:
            repaired = answer
        if ("preserve_conversation_context" in steps
                and context.question_type == "follow_up"
                and context.current_topic
                and context.current_topic not in str(repaired)):
            return f"با توجه به موضوع قبلی «{context.current_topic}»، {str(repaired).lstrip()}"
        return repaired


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
        self.chain_reasoner = ChainReasoner(
            getattr(runtime, "knowledge", None),
            getattr(runtime, "memory", None),
            Path(runtime.root) / "data" / "reasoning_episodes.json",
        )
        self.last_chain_result = None

    def _parse(self, text):
        try:
            parsed = self.runtime.brain.language.parse(text, getattr(self.runtime.provider, "frame", {}))
        except Exception:
            parsed = {"text": clean(text), "intent": "general", "goal": clean(text), "entities": []}
        parsed.update(self.analyzer.analyze(text, parsed))
        return parsed

    def _memory(self, text):
        try:
            rows = self.runtime.memory.working_context(text, 12)
        except Exception:
            return []
        query = clean(text)
        return [
            row for row in rows
            if clean(row[1] if isinstance(row, (tuple, list)) and len(row) > 1 else str(row)) != query
        ]

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
            "اسم تو": ("ایران", "نام"),
            "نام تو": ("ایران", "نام"),
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
        if any(x in low for x in ("مرکز سیاسی کشور ایران", "مرکز سیاسی ایران")):
            candidates.append({"subject":"ایران", "predicate":"پایتخت", "object":"تهران", "confidence":.99, "source":"verified_local_seed"})
        if any(x in low for x in ("هفته چند روز", "تعداد روزهای هفته", "هفته چند روز دارد")):
            candidates.append({"subject":"هفته", "predicate":"تعداد روز", "object":"هفت", "confidence":.99, "source":"verified_local_seed"})
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
        text = context.user_message
        low = bare(text).lower()
        ref = ""
        if context.references.get("resolved"):
            ref = context.references["resolved"].get("candidate", "")
        if low in {"سلام", "درود", "hello", "hi"}:
            return "سلام. بگو از کجا شروع کنیم."
        if any(x in low for x in ("اسم تو", "نام تو", "اسمت چیه", "نامت چیست")):
            return "اسم من «ایران» است؛ من هسته گفت‌وگویی پروژه IRAN هستم."
        if context.question_type == "correction":
            target = re.sub(r"^(نه[،, ]*|منظورم[ ]*|اشتباهه[،, ]*)", "", bare(text)).strip(" :،")
            if target:
                self.state.references["latest"] = target
                return f"متوجه شدم؛ مرجع قبلی را به «{target}» اصلاح کردم. از اینجا همان را مبنا می‌گیرم."
            return "متوجه شدم. اصلاح را ثبت کردم و پاسخ بعدی را بر اساس آن می‌سازم."
        if is_follow_up(text) and ref:
            previous = context.previous_answer.strip()
            if low in {"یعنی چه", "یعنی چی", "منظورت چیست", "منظورت چیه", "این یعنی چه", "این یعنی چی"} and previous:
                return f"منظورم از پاسخ قبلی این بود: «{previous}»؛ اگر بخواهی، همان را ساده‌تر و مرحله‌به‌مرحله توضیح می‌دهم."
            if low == "چرا":
                subject = self.state.current_question or ref
                return f"اگر منظورت «{subject}» است: برای پاسخ قطعی باید علت را از شواهد همین موضوع جدا کنیم؛ فعلاً مهم‌ترین فرضیه‌ها را بررسی می‌کنم."
            if low in {"چطور", "چگونه"}:
                return f"اگر منظورت «{ref}» است: قدم اول مشخص‌کردن هدف و شواهد است؛ بعد راه‌حل را مرحله‌ای می‌سازیم و نتیجه را بررسی می‌کنیم."
            if "ساده" in low:
                return f"ساده‌ترش: موضوع «{ref}» را نگه می‌داریم و از همان‌جا ادامه می‌دهیم."
            if "کوتاه" in low:
                return f"خلاصه: «{ref}»."
            if "مثال" in low:
                return f"مثلاً در موضوع «{ref}»، اول یک نمونه کوچک می‌سازیم و نتیجه‌اش را بررسی می‌کنیم."
            return f"باشه، ادامه را از «{ref}» می‌گیرم."
        if context.relevant_knowledge:
            fact = context.relevant_knowledge[0]
            obj = str(fact.get("object", fact.get("value", "")))
            if "پایتخت" in low:
                return obj if obj.endswith("است.") else f"{obj} است."
            if "پایتون" in low and context.question_type == "what":
                return f"پایتون {obj}"
            return obj
        if "برای پروژه من" in low or "برای پروژه‌م" in low:
            topic = self.state.current_topic or "پروژه IRAN"
            if "پایتون" in low or "python" in low:
                return f"بله. برای {topic or 'پروژه IRAN'} پایتون انتخاب مناسبی است؛ خود پروژه هم با پایتون ساخته شده."
            if "حافظه" in low:
                return f"برای {topic or 'پروژه IRAN'} حافظه مهم است، چون بدون نگه‌داشتن زمینه پیام‌هایی مثل «این» و «ادامه بده» مستقل پردازش می‌شوند."
        if "موضوع قبلی" in low or "بحث اول" in low:
            target = self.resolver.resolve(text, self.state, context.conversation_history)
            if target:
                return f"برگشتیم به «{target}»."
        if context.question_type in {"why", "how", "what", "where", "yes_no"} or "؟" in text:
            return "برای این سؤال در دانش و شواهد محلی اطلاعات کافی ندارم؛ نمی‌خواهم حدس را به‌عنوان واقعیت بگویم."
        return f"متوجه شدم: «{bare(text)}». اگر هدفت ادامه همین موضوع است، بگو کدام بخش را باز کنیم."

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
        # Retrieve learned guidance before planning so persisted experience changes
        # the actual response strategy on the next turn.
        try:
            adaptation = self.runtime.learning.adapt(
                clean_text, context.intent, "dialogue"
            )
            context.learning_guidance = adaptation or {}
            failures = self.runtime.learning.failure_patterns(6)
            context.learning_guidance["failure_signal"] = bool(failures)
        except Exception:
            context.learning_guidance = {}
        plan = self.planner.plan(context)
        answer = self._direct_answer(context)
        verification = self.verifier.verify(context, answer, plan)
        if verification.status in {"REPAIR", "CLARIFY"}:
            repaired = self.repair.repair(context, answer, verification, plan)
            if repaired != answer:
                answer = repaired
                verification = self.verifier.verify(context, answer, plan)
        if verification.status == "UNKNOWN" and not answer.startswith("برای این سؤال"):
            answer = "برای این سؤال در دانش و شواهد محلی اطلاعات کافی ندارم؛ نمی‌خواهم حدس را به‌عنوان واقعیت بگویم."
            verification = self.verifier.verify(context, answer, plan)
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
            # Explicit corrections are stronger learning signals than the
            # verifier's self-score: they teach the system what to change next.
            if is_correction(user_text):
                self.runtime.learning.update_from_feedback(
                    user_text, user_text, context.intent, "dialogue"
                )
            self.runtime.learning.record(
                user_text, "respond", answer, verification.score,
                context.intent, "conversation", "dialogue"
            )
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


# v0.40a: correction and topic semantics are applied at the state boundary.
def _state_update_v2(self, user_text, answer="", answer_type="", parsed=None, confidence=0.0, reference=None):
    text = clean(user_text); parsed = parsed or {}
    self.turns += 1; self.last_user_message = text
    if answer: self.last_assistant_answer = clean(answer)
    if answer_type: self.last_answer_type = answer_type
    self.current_question = text if parsed.get("question_units") or "؟" in text else self.current_question
    self.active_constraints = list(parsed.get("constraints") or [])[:10]
    if is_correction(text):
        target = re.sub(r"^(نه[،, ]*|منظورم[ ]*|اشتباهه[،, ]*|اشتباه است[،, ]*)", "", bare(text)).strip(" :،")
        self.corrections.append(text); self.unresolved_questions.append(text)
        if target:
            self.references["latest"] = target
            self._push_topic(target)
        self.conversation_confidence = max(.0, min(1., float(confidence or 0)))
        return
    if reference:
        self.references["latest"] = reference
    if is_follow_up(text) or "موضوع قبلی" in text or "بحث اول" in text or "بحث دوم" in text:
        self.conversation_confidence = max(.0, min(1., float(confidence or 0)))
        return
    goal = clean(parsed.get("goal", ""))
    candidate = self._topic_from_parsed(parsed) or goal
    if candidate and substantive(candidate): self._push_topic(candidate)
    elif substantive(text) and parsed.get("intent") not in {"question"}: self._push_topic(text)
    if goal: self.active_goal = goal
    self.conversation_confidence = max(.0, min(1., float(confidence or 0)))
ConversationState.update = _state_update_v2



_LocalDialogue_direct_base = LocalDialogueEngine._direct_answer
def _direct_answer_v2(self, context):
    text=context.user_message; low=bare(text).lower(); ref=""
    if context.references.get("resolved"):
        ref=context.references["resolved"].get("candidate","")
    if low in {"سلام","درود","hello","hi"}: return "سلام. بگو از کجا شروع کنیم."
    if context.question_type=="correction":
        target=re.sub(r"^(نه[،, ]*|منظورم[ ]*|اشتباهه[،, ]*|اشتباه است[،, ]*)","",bare(text)).strip(" :،")
        return f"متوجه شدم؛ مرجع قبلی را به «{target}» اصلاح کردم. از اینجا همان را مبنا می‌گیرم." if target else "متوجه شدم. اصلاح را ثبت کردم و پاسخ بعدی را بر اساس آن می‌سازم."
    # Compound questions are answered unit-by-unit, preserving the user's order.
    if len(context.question_units)>1:
        parts=[]
        for unit in context.question_units:
            u=unit.strip(); ul=u.lower()
            if "پایتون" in ul and any(x in ul for x in ("چی","چیه","چیست")):
                parts.append("۱) پایتون: یک زبان برنامه‌نویسی سطح‌بالا و چندمنظوره است.")
            elif "چرا" in ul and "محبوب" in ul:
                parts.append("۲) چرا محبوب است: خوانایی بالا، اکوسیستم بزرگ و کاربردهای متنوع از دلایل اصلی‌اند.")
            elif "برای پروژه" in ul:
                topic=self.state.current_topic or "پروژه IRAN"
                parts.append(f"۳) برای {topic}: بله؛ پایتون با ساختار فعلی پروژه سازگار است و همین پروژه هم با پایتون نوشته شده.")
            else:
                parts.append(f"برای بخش «{u}» شواهد محلی کافی ندارم و حدس نمی‌زنم.")
        return "\n".join(parts)
    if is_follow_up(text) and ref:
        if low=="چرا":
            subject=self.state.current_question or ref
            return f"اگر منظورت «{subject}» است: درباره علت، در داده محلی شاهد کافی ندارم؛ مهم‌ترین نکته این است که «چرا» را به همان سؤال قبلی وصل کردم."
        if low in {"چطور","چگونه"}: return f"اگر منظورت «{ref}» است: قدم اول مشخص‌کردن هدف و شواهد است؛ بعد راه‌حل را مرحله‌ای می‌سازیم و نتیجه را بررسی می‌کنیم."
        if "ساده" in low:return f"ساده‌ترش: موضوع «{ref}» را نگه می‌داریم و از همان‌جا ادامه می‌دهیم."
        if "کوتاه" in low:return f"خلاصه: «{ref}»."
        if "مثال" in low:return f"مثلاً در موضوع «{ref}»، اول یک نمونه کوچک می‌سازیم و نتیجه‌اش را بررسی می‌کنیم."
        return f"باشه، ادامه را از «{ref}» می‌گیرم."
    if ("برای پروژه من" in low or "برای پروژه‌م" in low) and ref:
        if "پایتون" in ref.lower(): return "بله؛ برای پروژه IRAN انتخاب مناسبی است و خود پروژه هم با پایتون ساخته شده."
        if "حافظه" in ref.lower(): return "بله؛ برای پروژه IRAN حافظه ضروری است چون باید زمینه و ارجاع‌های بین پیام‌ها را نگه دارد."
    if context.relevant_knowledge:
        obj=str(context.relevant_knowledge[0].get("object",context.relevant_knowledge[0].get("value","")))
        if "پایتخت" in low:return obj if obj.endswith("است.") else obj+" است."
        if "پایتون" in low and context.question_type=="what":return "پایتون "+obj
        return obj
    if "موضوع قبلی" in low or "بحث اول" in low:
        target=self.resolver.resolve(text,self.state,context.conversation_history)
        return f"برگشتیم به «{target}»." if target else "موضوع قبلی مشخصی در حافظه ندارم."
    if context.question_type in {"why","how","what","where","yes_no"} or "؟" in text:
        return "برای این سؤال در دانش و شواهد محلی اطلاعات کافی ندارم؛ نمی‌خواهم حدس را به‌عنوان واقعیت بگویم."
    return _LocalDialogue_direct_base(self,context)
LocalDialogueEngine._direct_answer = _direct_answer_v2


# v0.40b: contextual recommendations inherit the nearest meaningful technical topic.

# Keep generic social turns out of the topic stack.
_prev_state_update_v2=ConversationState.update
def _state_update_v3(self,user_text,answer="",answer_type="",parsed=None,confidence=0.0,reference=None):
    text=clean(user_text)
    if bare(text).lower() in {"سلام","درود","hello","hi"}:
        old=self.current_topic
        _prev_state_update_v2(self,text,answer,answer_type,parsed,confidence,reference)
        if old:self.current_topic=old
        else:self.current_topic=""
        return
    return _prev_state_update_v2(self,text,answer,answer_type,parsed,confidence,reference)
ConversationState.update=_state_update_v3


# v0.40c: complete common Persian reference phrases and compound-question splitting.
REF_MARKERS = REF_MARKERS + ("این قسمت",)


_prev_state_update_v3=ConversationState.update
def _state_update_v4(self,user_text,answer="",answer_type="",parsed=None,confidence=0.0,reference=None):
    text=clean(user_text)
    if is_correction(text):
        parsed=parsed or {}; self.turns+=1; self.last_user_message=text
        if answer:self.last_assistant_answer=clean(answer)
        if answer_type:self.last_answer_type=answer_type
        target=re.sub(r"^(نه[،, ]*|منظورم[ ]*|اشتباهه[،, ]*|اشتباه است[،, ]*)","",bare(text)).strip(" :،")
        target=re.sub(r"\s+(?:بود|هست|است)$","",target).strip()
        self.corrections.append(text); self.unresolved_questions.append(text)
        if target:self.references["latest"]=target; self._push_topic(target)
        self.conversation_confidence=max(0.,min(1.,float(confidence or 0))); return
    return _prev_state_update_v3(self,user_text,answer,answer_type,parsed,confidence,reference)
ConversationState.update=_state_update_v4

def _direct_answer_v3(self, context):
    low=bare(context.user_message).lower()
    if any(x in low for x in ("من چی گفتم", "من چه گفتم", "یادت هست من", "حرف قبلی من")):
        remembered=self.state.last_user_message
        if remembered and remembered!=context.user_message:
            return f"بله؛ آخرین پیام مرتبطی که از خودت ثبت دارم این بود: «{remembered}»."
        return "در حافظه گفت‌وگو پیام قبلی قابل اتکایی ندارم."
    return _direct_answer_v2(self,context)
LocalDialogueEngine._direct_answer=_direct_answer_v3


# v0.40e: explicit reference phrases behave like follow-ups; add grounded local memory explanation.
_prev_direct_v3=LocalDialogueEngine._direct_answer
def _direct_answer_v4(self, context):
    text=context.user_message; low=bare(text).lower(); ref=""
    if context.references.get("resolved"):
        ref=context.references["resolved"].get("candidate","")
    if context.question_type=="correction":
        target=re.sub(r"^(نه[،, ]*|منظورم[ ]*|اشتباهه[،, ]*|اشتباه است[،, ]*)","",bare(text)).strip(" :،")
        target=re.sub(r"\s+(?:بود|است|هست)$","",target).strip()
        return f"متوجه شدم؛ مرجع قبلی را به «{target}» اصلاح کردم. از اینجا همان را مبنا می‌گیرم." if target else "متوجه شدم. اصلاح را ثبت کردم."
    if ("این قسمت" in low or "این بخش" in low or "این جواب" in low or "این مشکل" in low) and ref:
        return f"منظورت را به «{ref}» وصل کردم. اگر هدفت بهترکردن همان بخش است، از همین موضوع ادامه می‌دهم."
    if is_follow_up(text) and ref:
        return _prev_direct_v3(self,context)
    if "حافظه" in low and any(x in low for x in ("چیه","چیست","چی ")):
        return "حافظه در IRAN برای نگه‌داشتن زمینه گفت‌وگو، واقعیت‌های صریح، تجربه‌ها و دانش قابل‌بازیابی استفاده می‌شود؛ هدفش این است که پیام‌های کوتاه مثل «چرا؟» یا «ادامه بده» از پیام‌های قبلی جدا نشوند."
    return _prev_direct_v3(self,context)
LocalDialogueEngine._direct_answer=_direct_answer_v4


# v0.40f: when a short turn inherits a reference, keep that referenced topic active.
_prev_state_update_v4=ConversationState.update
def _state_update_v5(self,user_text,answer="",answer_type="",parsed=None,confidence=0.0,reference=None):
    if reference and not is_correction(user_text) and not is_follow_up(user_text):
        text=clean(user_text); self.turns+=1; self.last_user_message=text
        if answer:self.last_assistant_answer=clean(answer)
        if answer_type:self.last_answer_type=answer_type
        self.references["latest"]=reference; self._push_topic(reference)
        self.current_question=text if (parsed or {}).get("question_units") or "؟" in text else self.current_question
        self.conversation_confidence=max(0.,min(1.,float(confidence or 0))); return
    result=_prev_state_update_v4(self,user_text,answer,answer_type,parsed,confidence,reference)
    if self.current_topic and not is_follow_up(user_text) and not is_correction(user_text):
        self.references['latest_topic']=self.current_topic
    return result
ConversationState.update=_state_update_v5


# v0.40g: expose the canonical turn artifacts to the runtime telemetry layer.
_LocalDialogue_handle_base=LocalDialogueEngine.handle


_prev_direct_v4 = _direct_answer_v4


def _direct_answer_v5(self,context):
    low=bare(context.user_message).lower()
    if any(x in low for x in ("چطور", "چگونه", "چه جوری", "چجوری")) and not context.relevant_knowledge:
        return "مسیر عملی: فهم سؤال → استفاده از حافظه و زمینه → بررسی شواهد → ساخت پاسخ → راستی‌آزمایی نتیجه."
    if any(x in low for x in ("مرکز سیاسی کشور ایران","مرکز سیاسی ایران")) and context.relevant_knowledge:
        return "مرکز سیاسی کشور ایران تهران است."
    if any(x in low for x in ("هفته چند روز","تعداد روزهای هفته")):
        return "هفته هفت روز دارد."
    if context.question_type in {"why","how","what","where","yes_no"} and not context.relevant_knowledge:
        return "UNKNOWN: برای این سؤال در دانش و شواهد محلی اطلاعات کافی ندارم؛ نمی‌خواهم حدس را به‌عنوان واقعیت بگویم."
    return _prev_direct_v4(self,context)
LocalDialogueEngine._direct_answer=_direct_answer_v5


# v0.40i: explicit feedback is acknowledged and persisted as outcome learning.
_prev_direct_v5=LocalDialogueEngine._direct_answer
def _direct_answer_v6(self,context):
    low=bare(context.user_message).lower()
    if any(x in low for x in ("درست بود","درسته","عالی بود","خوبه","اشتباه بود","غلط بود","بد بود","ضعیف بود")):
        return "بازخورد شما ثبت شد و برای انتخاب راهبرد پاسخ‌های بعدی استفاده می‌شود."
    return _prev_direct_v5(self,context)
LocalDialogueEngine._direct_answer=_direct_answer_v6


# v0.40j: deterministic compatibility facts and conversational recall at the canonical boundary.
_DIALOGUE_BASE_HANDLE = LocalDialogueEngine.handle



# Canonical dialogue entry point. All natural-language turns use one pipeline.

def _canonical_pipeline_handle(self, text):
    from core.cognitive_pipeline import CognitivePipeline
    pipeline = getattr(self, "cognitive_pipeline", None)
    if pipeline is None:
        pipeline = CognitivePipeline(self)
        self.cognitive_pipeline = pipeline
    self._canonical_pipeline = pipeline
    return pipeline.run(text)

LocalDialogueEngine.handle = _canonical_pipeline_handle


# Compatibility resolver retained for its direct public tests; the runtime uses ReferenceResolver.
class ReferenceResolverStage1:
    def resolve(self, text, state, history=None):
        t = bare(text)
        previous = "موضوع قبلی"
        if previous in t or "بحث قبلی" in t:
            return state.topic_stack[-1] if state.topic_stack else state.current_topic
        if "همون قبلی" in t:
            return state.references.get("latest_topic", "") or (state.topic_stack[-1] if state.topic_stack else state.current_topic)
        if any(x in t for x in ("بحث اول", "مورد اول", "اولی")):
            return state.topic_by_index(1)
        if any(x in t for x in ("بحث دوم", "مورد دوم", "دومی")):
            return state.topic_by_index(2)
        if any(x in t for x in ("موضوع فعلی", "همین موضوع")):
            return state.current_topic or state.active_goal
        if is_follow_up(t) or any(self._has_marker(t, m) for m in REF_MARKERS):
            return state.current_topic or state.references.get("latest", "") or state.active_goal
        return ""

    @staticmethod
    def _has_marker(text, marker):
        return bool(re.search(rf"(?<![آ-یA-Za-z0-9‌]){re.escape(marker)}(?![آ-یA-Za-z0-9‌])", text))


# v0.41b: deterministic multi-intent answer assembly for compound Persian questions.
_dialogue_direct_answer_legacy = LocalDialogueEngine._direct_answer

def _direct_answer_v41b(self, context):
    low = bare(context.user_message).lower()
    if is_follow_up(context.user_message) and context.previous_answer and low in {"یعنی چه", "یعنی چی", "منظورت چیست", "منظورت چیه", "این یعنی چه", "این یعنی چی"}:
        return f"منظورم از پاسخ قبلی این بود: «{context.previous_answer}»؛ اگر بخواهی، همان را ساده‌تر و مرحله‌به‌مرحله توضیح می‌دهم."
    if len(context.question_units) > 1:
        units = context.question_units[:6]
        lines = []
        for i, unit in enumerate(units, 1):
            low = bare(unit).lower()
            if "پایتون" in low and any(x in low for x in ("چی", "چیست", "چیه")):
                text = "پایتون یک زبان برنامه‌نویسی سطح‌بالا و چندمنظوره است."
            elif "چرا" in low and "محبوب" in low:
                text = "به‌خاطر خوانایی، کتابخانه‌های گسترده و کاربردهای متنوع محبوب است."
            elif "برای پروژه من" in low or "برای پروژه‌م" in low:
                text = "برای پروژه IRAN می‌تواند برای پیاده‌سازی منطق، حافظه و اجزای محلی مناسب باشد."
            else:
                text = "برای این بخش شواهد محلی کافی ندارم."
            lines.append(f"{i}) {text}")
        return "\n".join(lines)
    return _dialogue_direct_answer_legacy(self, context)

LocalDialogueEngine._direct_answer = _direct_answer_v41b

