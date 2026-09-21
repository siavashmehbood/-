"""Deterministic contradiction and answer-quality checks for local IRAN runtime."""
from dataclasses import dataclass, field
import re


@dataclass
class VerificationResult:
    accepted: bool
    score: float
    reasons: list = field(default_factory=list)
    contradictions: list = field(default_factory=list)
    status: str = "PASS"


class SemanticVerifier:
    """Checks answer consistency against the current question and known constraints."""

    STOP = {"و", "یا", "که", "را", "به", "از", "در", "برای", "با", "این", "آن"}

    ALIASES = {
        'نام':'اسم', 'اسمم':'اسم', 'نامم':'اسم', 'name':'اسم',
        'کارم':'کار', 'work_on':'کار',
        'ساخته':'ساخت', 'بفهمی':'فهم', 'بفهمد':'فهم', 'فهمیدن':'فهم',
        'creator':'سازنده', 'iran':'ایران', 'پایتون':'python',
    }

    @classmethod
    def tokens(cls, text):
        normalized = str(text or "").lower().replace('ي', 'ی').replace('ك', 'ک')
        normalized = re.sub(r'مرکز\s+سیاسی(?:\s+کشور)?', 'پایتخت', normalized)
        words = re.findall(r"[\wآ-ی]+", normalized)
        return {cls.ALIASES.get(w, w) for w in words if len(w) > 1 and w not in cls.STOP}

    @classmethod
    def overlap(cls, a, b):
        x, y = cls.tokens(a), cls.tokens(b)
        return len(x & y) / max(1, len(x | y))

    def verify(self, question, answer, constraints=None, rejected_answers=None, evidence=None):
        constraints = constraints or []
        rejected_answers = rejected_answers or []
        reasons = []
        contradictions = []
        q = str(question or "").strip()
        a = str(answer or "").strip()
        if not a:
            return VerificationResult(False, 0.0, ["empty_answer"], [], "CLARIFY")
        if a.startswith("UNKNOWN:"):
            return VerificationResult(True, .35, ['insufficient_evidence'], [], 'UNKNOWN')
        # Question operators must not make two unrelated topics appear aligned.
        operators = {'چیست', 'چیه', 'کجاست', 'کجا', 'چه', 'چرا', 'چطور', 'چگونه',
                     'درباره', 'توضیح', 'بده', 'پاسخ', 'سؤال', 'است', 'هست', 'من', 'شما'}
        question_terms = self.tokens(q) - operators
        answer_terms = self.tokens(a) - operators
        asks_information = bool(re.search(r'[؟?]|چیست|چیه|کجاست|چگونه|چطور|چرا|توضیح\s+بده', q))
        profile_query = bool(re.search(r'(?:درباره\s+خودم|از\s+من).*(?:گفت|یاد)|خودم.*گفتم', q))
        relevant = []
        for fact in evidence or []:
            if not isinstance(fact, dict) or fact.get('contradicted_by'):
                continue
            anchor = self.tokens(str(fact.get('subject','')) + ' ' + str(fact.get('predicate',''))) - operators
            if (anchor and anchor <= question_terms) or (profile_query and fact.get('subject') == 'user'):
                relevant.append(str(fact.get('object', fact.get('value', ''))).strip())
        supported = any(value and self.tokens(value) and self.tokens(value) <= self.tokens(a) for value in relevant)
        aligned = bool(question_terms & answer_terms) or supported
        score = .72
        if asks_information and question_terms and not aligned:
            reasons.append('unrelated_answer')
            score = .4
        if relevant and not supported:
            contradictions.append('provided_evidence_not_used')
        if self.overlap(q, a) >= .08:
            score += .08
        else:
            reasons.append("low_question_alignment")
        low_a = a.lower()
        for constraint in constraints:
            c = str(constraint).lower()
            if c == "آفلاین" and any(x in low_a for x in ("api", "شبکه", "سرویس آنلاین", "cloud")):
                contradictions.append("offline_constraint")
            if c == "بدون api" and ("api" in low_a or "مدل آماده" in low_a):
                contradictions.append("no_api_constraint")
        if contradictions:
            score -= .45
            reasons.append("constraint_contradiction")
        for rejected in rejected_answers:
            if self.overlap(a, rejected) >= .72:
                contradictions.append("repeats_rejected_answer")
                score -= .35
                break
        score = max(0.0, min(1.0, score))
        accepted = score >= .70 and not contradictions
        return VerificationResult(accepted, score, reasons, contradictions, "PASS" if accepted else "REPAIR")
