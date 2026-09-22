"""Deterministic self-directed learning controller for IRAN.

No network, model, embedding, or external knowledge source is used here.
The controller turns a topic into a bounded learning plan and decides whether
new evidence is relevant, novel, conflicting, and worth learning.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
from persistence import atomic_write_json, load_critical_json


_STOP = set("the and or for with from this that are was were is of to in a an on as by".split())
_STOP |= set("و یا از برای با که این آن است را در به یک های هایِ درباره روی از".split())


@dataclass
class LearningGoal:
    goal_id: str
    topic: str
    gap: str
    objective: str
    priority: str
    status: str = "needs_evidence"
    domain: str = "general"
    attempts: int = 0
    evidence_count: int = 0
    success_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    stage: str = "foundation"
    assessments: list | None = None


class SelfDirectedLearning:
    """Goal-directed learning, gap detection, prioritization and consolidation."""

    def __init__(self, path=None, max_goals=500):
        self.max_goals = int(max_goals)
        self.path = Path(path) if path else None
        self.goals = []
        self.history = []
        self._load()

    @staticmethod
    def _tokens(text):
        words = re.findall(r"[\wآ-ی]+", str(text).lower())
        return {w for w in words if len(w) > 1 and w not in _STOP}

    @classmethod
    def relevance(cls, topic, text):
        a, b = cls._tokens(topic), cls._tokens(text)
        if not a or not b:
            return 0.0
        overlap = len(a & b) / len(a)
        coverage = len(a & b) / max(1, len(a | b))
        return round(min(1.0, overlap * .75 + coverage * .25), 4)

    @classmethod
    def novelty(cls, topic, evidence, known):
        rel = cls.relevance(topic, evidence)
        if not known:
            return rel
        known_tokens = cls._tokens(known)
        evidence_tokens = cls._tokens(evidence)
        if not evidence_tokens:
            return 0.0
        new = len(evidence_tokens - known_tokens) / len(evidence_tokens)
        return round(rel * new, 4)

    @classmethod
    def contradiction(cls, evidence, known):
        """Conservative conflict signal: shared subject terms + explicit negation."""
        if not evidence or not known:
            return 0.0
        e, k = str(evidence).lower(), str(known).lower()
        neg = (" نیست", " نمی ", " نادرست", " false", "not ", "never", "no ")
        e_neg = any(x in e for x in neg)
        k_neg = any(x in k for x in neg)
        shared = cls.relevance(e, k)
        if shared < .20 or e_neg == k_neg:
            return 0.0
        return round(min(1.0, shared), 4)

    @classmethod
    def detect_domain(cls, topic, evidence=""):
        text = f"{topic} {evidence}".lower()
        groups = {
            "programming": ("python", "پایتون", "کد", "برنامه", "حلقه", "تابع", "متغیر", "الگوریتم", "programming", "javascript", "java", "c++"),
            "computer_science": ("علوم کامپیوتر", "ساختمان داده", "پایگاه داده", "سیستم عامل", "شبکه", "امنیت", "مهندسی نرم افزار", "data structure", "database", "operating system"),
            "artificial_intelligence": ("هوش مصنوعی", "یادگیری ماشین", "یادگیری عمیق", "شبکه عصبی", "پردازش زبان", "بینایی ماشین", "ai", "machine learning", "deep learning"),
            "mathematics": ("ریاضی", "معادله", "جبر", "هندسه", "حسابان", "احتمال", "آمار", "منطق", "عدد", "math", "equation", "algebra", "calculus", "statistics"),
            "physics": ("فیزیک", "نیرو", "حرکت", "انرژی", "الکتریسیته", "مغناطیس", "مکانیک", "physics", "force", "energy"),
            "chemistry": ("شیمی", "اتم", "مولکول", "واکنش", "عنصر", "جدول تناوبی", "chemistry", "atom", "molecule"),
            "biology": ("زیست", "زیست شناسی", "سلول", "ژن", "ژنتیک", "تکامل", "بدن", "biology", "cell", "gene", "evolution"),
            "persian_literature": ("ادبیات فارسی", "فارسی", "نثر فارسی", "غزل", "مثنوی", "شاهنامه", "حافظ", "سعدی"),
            "english": ("انگلیسی", "english", "grammar", "vocabulary", "لغت", "گرامر", "مکالمه", "reading", "writing"),
            "english_literature": ("ادبیات انگلیسی", "شعر انگلیسی", "رمان انگلیسی", "شعر", "رمان", "تحلیل متن", "english literature", "poetry", "novel"),
            "arabic": ("عربی", "صرف", "نحو", "ترجمه عربی", "arabic"),
            "history": ("تاریخ", "ایران باستان", "تمدن", "جنگ", "انقلاب", "history", "civilization"),
            "geography": ("جغرافیا", "اقلیم", "جمعیت", "قاره", "کشور", "geography", "climate", "population"),
            "earth_science": ("زمین شناسی", "کانی", "سنگ", "زمین ساخت", "earth science", "geology"),
            "environmental_science": ("محیط زیست", "اکوسیستم", "آلودگی", "تغییر اقلیم", "environment", "ecology"),
            "philosophy": ("فلسفه", "منطق فلسفی", "اخلاق", "هستی", "معرفت", "philosophy", "ethics", "epistemology"),
            "psychology": ("روانشناسی", "شناخت", "رفتار", "یادگیری", "روان", "psychology", "behavior", "cognition"),
            "sociology": ("جامعه شناسی", "جامعه", "فرهنگ", "نهاد اجتماعی", "sociology", "society", "culture"),
            "economics": ("اقتصاد", "تورم", "عرضه", "تقاضا", "بازار", "economics", "inflation", "market"),
            "law": ("حقوق", "قانون", "قرارداد", "جرم", "مدنی", "کیفری", "law", "contract", "criminal"),
            "general": ("دانش", "مفهوم", "تعریف", "general"),
        }
        scores = {d: sum(1 for w in words if w in text) for d, words in groups.items()}
        best = max(scores, key=scores.get) if scores else "general"
        return best if scores.get(best, 0) else "general"

    CURRICULUM = {
        "astronomy": ["منظومه شمسی", "ستاره ها", "کهکشان ها", "کیهان شناسی"],
        "logic": ["گزاره", "استنتاج", "منطق محمولات"],
        "mathematics": ["اعداد و محاسبات", "کسر و درصد", "جبر پایه", "معادلات", "هندسه", "توابع", "حسابان", "احتمال", "آمار", "منطق ریاضی"],
        "programming": ["مبانی برنامه نویسی", "Python", "متغیر و نوع داده", "شرط و حلقه", "تابع", "ساختمان داده", "الگوریتم", "خطایابی", "تست نرم افزار", "طراحی نرم افزار"],
        "computer_science": ["مبانی علوم کامپیوتر", "ساختمان داده", "الگوریتم", "پایگاه داده", "سیستم عامل", "شبکه", "امنیت", "مهندسی نرم افزار", "معماری کامپیوتر"],
        "artificial_intelligence": ["مبانی هوش مصنوعی", "جستجو و حل مسئله", "منطق و استدلال", "یادگیری ماشین", "یادگیری عمیق", "شبکه عصبی", "پردازش زبان طبیعی", "بینایی ماشین", "ارزیابی و ایمنی هوش مصنوعی", "یادگیری خودمختار"],
        "physics": ["مبانی فیزیک", "حرکت و نیرو", "انرژی", "الکتریسیته", "مغناطیس", "موج و نور"],
        "chemistry": ["ساختار اتم", "پیوند شیمیایی", "واکنش ها", "استوکیومتری", "اسید و باز", "شیمی آلی مقدماتی"],
        "biology": ["سلول", "ژنتیک", "تکامل", "بدن انسان", "بوم شناسی", "زیست مولکولی مقدماتی"],
        "persian_literature": ["واژگان و املا", "دستور زبان فارسی", "آرایه های ادبی", "عروض و قافیه", "تاریخ ادبیات", "شعر و نثر فارسی", "درک و تحلیل متن"],
        "english": ["واژگان پایه", "گرامر پایه", "جمله سازی", "خواندن", "شنیدن", "نوشتن", "مکالمه", "گرامر پیشرفته"],
        "english_literature": ["داستان کوتاه", "شعر انگلیسی", "رمان و روایت", "تحلیل متن", "سبک و آرایه", "تاریخ ادبیات انگلیسی"],
        "arabic": ["واژگان پایه", "صرف", "نحو", "ترجمه", "درک متن عربی"],
        "history": ["تاریخ ایران", "تاریخ جهان", "تمدن ها", "تحولات سیاسی و اجتماعی", "تاریخ معاصر"],
        "geography": ["نقشه و مکان", "جمعیت", "اقلیم", "جغرافیای ایران", "جغرافیای جهان"],
        "earth_science": ["زمین شناسی مقدماتی", "سنگ ها و کانی ها", "زمین ساخت", "چرخه های زمین"],
        "environmental_science": ["اکوسیستم", "تنوع زیستی", "آلودگی", "منابع طبیعی", "تغییر اقلیم"],
        "philosophy": ["مبانی فلسفه", "منطق", "معرفت شناسی", "اخلاق", "فلسفه علم"],
        "psychology": ["مبانی روانشناسی", "شناخت و حافظه", "یادگیری", "رفتار", "هیجان"],
        "sociology": ["مبانی جامعه شناسی", "گروه و جامعه", "نهادهای اجتماعی", "فرهنگ", "تغییر اجتماعی"],
        "economics": ["مبانی اقتصاد", "عرضه و تقاضا", "تورم", "بازار", "اقتصاد کلان مقدماتی"],
        "law": ["مبانی حقوق", "حقوق مدنی", "حقوق کیفری", "حقوق اساسی", "قراردادها", "آیین دادرسی"],
    }

    MODES = ("definition", "example", "application", "problem_solving", "comparison", "common_errors", "transfer_test", "review")

    def curriculum_batch(self, batch_size=24):
        """Generate a rotating deterministic stream of unique reviewable learning goals."""
        batch_size=max(1, min(200, int(batch_size)))
        rows=[]
        state={str(x.get("key")) for x in self.history if isinstance(x, dict) and x.get("type") == "curriculum_request"}
        buckets=[]
        for domain, topics in self.CURRICULUM.items():
            buckets.append([(domain, topic, mode) for topic in topics for mode in self.MODES])
        topics=[item for bucket in buckets for item in bucket]
        for index in range(max((len(bucket) for bucket in buckets), default=0)):
            for bucket in buckets:
                if index >= len(bucket): continue
                domain, topic, mode=bucket[index]
                key=f"{domain}|{topic}|{mode}"
                if key in state: continue
                rows.append({"key":key,"domain":domain,"topic":topic,"mode":mode,
                             "objective":f"build_verified_understanding:{topic}:{mode}",
                             "source":"self_directed_curriculum"})
                if len(rows) >= batch_size: break
            if len(rows) >= batch_size: break
        if len(rows) < batch_size:
            for domain, topic, mode in topics:
                key=f"{domain}|{topic}|{mode}"
                if key in {r["key"] for r in rows}: continue
                rows.append({"key":key,"domain":domain,"topic":topic,"mode":mode,
                             "objective":f"build_verified_understanding:{topic}:{mode}",
                             "source":"self_directed_curriculum"})
                if len(rows) >= batch_size: break
        now=datetime.now().isoformat(timespec="seconds")
        self.history.extend({"type":"curriculum_request","key":r["key"],"time":now} for r in rows)
        self.history=self.history[-2000:]
        self._save()
        return rows

    @staticmethod
    def _stable_id(topic, gap, objective):
        raw = f"{topic}|{gap}|{objective}".encode("utf-8")
        return "goal_" + hashlib.sha256(raw).hexdigest()[:16]

    def _save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"goals": [asdict(g) for g in self.goals], "history": self.history[-2000:]}
        atomic_write_json(self.path, payload)

    def _load(self):
        if not self.path:
            return
        payload = load_critical_json(self.path, {})
        self.goals = [LearningGoal(**r) for r in payload.get("goals", [])[-self.max_goals:]]
        self.history = payload.get("history", [])[-2000:]

    def create_goal(self, topic, gap="دانش مرتبط کامل نیست", objective=None,
                    priority="medium", domain=None):
        topic = str(topic).strip()
        domain = domain or self.detect_domain(topic)
        objective = objective or f"تکمیل دانش درباره {topic}"
        gid = self._stable_id(topic, gap, objective)
        existing = next((g for g in self.goals if g.goal_id == gid), None)
        now = datetime.now().isoformat(timespec="seconds")
        if existing:
            existing.updated_at = now
            return asdict(existing)
        goal = LearningGoal(gid, topic, str(gap), str(objective), str(priority),
                            domain=domain, created_at=now, updated_at=now)
        self.goals.append(goal)
        self.goals = self.goals[-self.max_goals:]
        self._save()
        return asdict(goal)

    def plan_turn(self, text, parsed=None, current_topic="", known_text=""):
        """Create a bounded learning goal from a live question without injecting domain knowledge."""
        parsed = parsed or {}
        question_type = str(parsed.get("question_type", "general"))
        if known_text.strip(): return None
        if question_type not in {"what", "why", "how", "where", "yes_no"}:
            return None
        topic = str(current_topic or "").strip() or str(parsed.get("topic", "")).strip() or str(text or "").strip()
        if not topic:
            return None
        goal = self.create_goal(topic, gap="question_requires_grounded_knowledge", objective=f"build_verified_understanding_of:{topic}", priority="medium", domain=self.detect_domain(topic))
        return {"goal": goal, "next_action": self.next_action(goal), "known_context": bool(known_text)}
    def assess(self, topic, evidence_text, known_text="", source_confidence=0.0):
        rel = self.relevance(topic, evidence_text)
        nov = self.novelty(topic, evidence_text, known_text)
        conflict = self.contradiction(evidence_text, known_text)
        confidence = max(0.0, min(1.0, float(source_confidence)))
        repeated = bool(known_text) and nov < .08
        useful = rel >= .22 and confidence >= .35 and (nov >= .08 or conflict >= .35 or not known_text)
        if rel < .22: reason = "topic_mismatch"
        elif confidence < .35: reason = "weak_evidence"
        elif repeated and conflict < .35: reason = "already_known_or_low_novelty"
        elif conflict >= .35: reason = "relevant_conflict_requires_resolution"
        else: reason = "relevant_gap_candidate"
        priority_score = rel * .45 + nov * .30 + conflict * .20 + confidence * .05
        priority = "high" if priority_score >= .62 or conflict >= .60 else "medium" if priority_score >= .36 else "low"
        return {"learn": useful, "topic": str(topic), "domain": self.detect_domain(topic, evidence_text),
                "relevance": rel, "novelty": nov, "contradiction": conflict,
                "source_confidence": round(confidence, 4), "priority": priority,
                "reason": reason, "needs_resolution": conflict >= .35}

    def goal_for(self, topic, evidence_text="", known_text="", source_confidence=0.0):
        decision = self.assess(topic, evidence_text, known_text, source_confidence)
        gap = ("حل اختلاف شواهد درباره موضوع" if decision["needs_resolution"] else
               "شکاف دانشی مرتبط با موضوع" if decision["learn"] else decision["reason"])
        goal = self.create_goal(topic, gap, f"تکمیل و راستی‌آزمایی دانش درباره {str(topic).strip()}",
                                decision["priority"], decision["domain"])
        goal["decision"] = decision
        return goal

    def next_action(self, goal_or_topic):
        topic = goal_or_topic.get("topic", "") if isinstance(goal_or_topic, dict) else str(goal_or_topic)
        candidates = [g for g in self.goals if g.topic == topic]
        if not candidates:
            return {"action": "define_goal", "topic": topic}
        g = candidates[-1]
        if g.status == "needs_evidence": return {"action": "collect_relevant_evidence", "goal_id": g.goal_id}
        if g.status == "conflict": return {"action": "resolve_conflict", "goal_id": g.goal_id}
        if g.status == "testing": return {"action": "run_knowledge_test", "goal_id": g.goal_id}
        return {"action": "review_or_expand", "goal_id": g.goal_id}

    def update_outcome(self, goal_id, status, evidence_count=None, success=False):
        goal = next((g for g in self.goals if g.goal_id == goal_id), None)
        if not goal: return None
        goal.status = str(status)
        goal.attempts += 1
        if evidence_count is not None: goal.evidence_count += int(evidence_count)
        if success: goal.success_count += 1
        goal.updated_at = datetime.now().isoformat(timespec="seconds")
        self.history.append({"goal_id": goal_id, "status": status, "success": bool(success), "at": goal.updated_at})
        self._save()
        return asdict(goal)

    def prioritize(self, limit=10):
        def score(g):
            base = {"high": .9, "medium": .55, "low": .25}.get(g.priority, .25)
            urgency = 1.0 if g.status in {"needs_evidence", "conflict"} else .55
            return base * .65 + urgency * .25 + min(1.0, g.attempts / 10) * .10
        rows = sorted(self.goals, key=score, reverse=True)
        return [{"goal": asdict(g), "priority_score": round(score(g), 4),
                 "next_action": self.next_action(asdict(g))} for g in rows[:int(limit)]]

    STAGES = ("foundation", "intermediate", "advanced", "practice", "evaluation", "consolidation")

    def observe_gap(self, question, reason):
        topic = re.sub(r"\s+", " ", str(question)).strip()
        if len(topic) < 4: return None
        existing = next((g for g in self.goals if g.topic == topic), None)
        if existing:
            return asdict(existing)
        return self.create_goal(topic, gap=str(reason), objective="find_supported_answer:"+topic,
                                priority="high", domain=self.detect_domain(topic))

    def next_curriculum_goals(self, domains=None, limit=8):
        result=[]
        for domain in (domains or self.CURRICULUM):
            for topic in self.CURRICULUM.get(domain, []):
                old = next((g for g in self.goals if g.topic == topic and g.domain == domain), None)
                if old:
                    # An existing curriculum goal is already the durable work item.
                    # Do not report it as freshly created on every supervisor cycle.
                    if old.status != "consolidated":
                        result.append(asdict(old))
                    break
                result.append(self.create_goal(topic, "curriculum", "demonstrate:"+topic, "medium", domain))
                break
            if len(result) >= max(1,min(int(limit),20)): break
        return result

    def record_assessment(self, goal_id, evidence_id, score, verified, kind="evaluation"):
        goal=next((g for g in self.goals if g.goal_id==goal_id),None)
        if goal is None: return None
        records=goal.assessments or []
        if kind not in {"evaluation", "retrieval"}:
            raise ValueError("unsupported assessment kind")
        if not evidence_id or any(r["id"]==evidence_id and r.get("kind", "evaluation")==kind for r in records):
            return asdict(goal)
        records.append({"id":evidence_id,"score":float(score),"verified":bool(verified),"stage":goal.stage,"kind":kind})
        goal.assessments=records
        if kind == "retrieval":
            # Recall demonstrates availability of a claim, not mastery of the
            # next curriculum stage. Keep its evidence without promoting it.
            self._save()
            return asdict(goal)
        if verified and score >= .8:
            index=self.STAGES.index(goal.stage)
            if index == len(self.STAGES)-1: goal.status="consolidated"
            else: goal.stage=self.STAGES[index+1];goal.status="needs_evidence"
        else: goal.status="needs_evidence"
        self._save(); return asdict(goal)

    def snapshot(self):
        return {"goals": [asdict(g) for g in self.goals], "count": len(self.goals),
                "priority_queue": self.prioritize(10), "history_count": len(self.history)}
