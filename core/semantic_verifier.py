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
    evidence_status: str = "NOT_ENOUGH_INFO"
    evidence_sources: list = field(default_factory=list)


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
        normalized = normalized.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫−', '01234567890123456789.-'))
        # Keep signed decimals atomic: a bag of digit fragments loses value
        # order and sign, and discarding one-character tokens loses 0..9.
        words = re.findall(r"-?\d+(?:\.\d+)?|[\wآ-ی]+", normalized)
        return {cls.ALIASES.get(w, w) for w in words
                if (len(w) > 1 or w.isdigit()) and w not in cls.STOP}

    @classmethod
    def overlap(cls, a, b):
        x, y = cls.tokens(a), cls.tokens(b)
        return len(x & y) / max(1, len(x | y))

    # Explicitly functional relations only: multiple preferences or claims
    # must never be mistaken for conflicting values of a single property.
    FUNCTIONAL = {"پایتخت", "capital", "نام", "name", "تعداد", "count", "radius", "شعاع"}

    def _grounding(self, answer, facts, profile_query=False):
        if not facts:
            return "NOT_ENOUGH_INFO", []
        groups = {}
        sources = []
        for fact in facts:
            sources.append(str(fact.get('source') or 'stored_fact'))
            sources.extend(str(row['source']) for row in fact.get('source_observations', [])
                           if isinstance(row, dict) and row.get('source'))
        sources = list(dict.fromkeys(sources))
        for fact in facts:
            predicate = str(fact.get('predicate', '')).strip().lower()
            if predicate in self.FUNCTIONAL or fact.get('cardinality') == 'one':
                key = (str(fact.get('subject', '')).strip().lower(), predicate)
                groups.setdefault(key, set()).add(str(fact.get('object', fact.get('value', ''))).strip())
        if any(len(values) > 1 for values in groups.values()):
            return "CONFLICTING", sources
        clauses = re.split(r'[؛;!؟\n]|(?<!\d)\.(?!\d)|[،,]', answer)
        support = False
        refuted = False
        filler = self.tokens('پاسخ مستقیم جواب است هست is answer direct')
        negatives = {'نیست', 'نبود', 'نباشد', 'not', 'never'}
        for fact in facts:
            value = self.tokens(fact.get('object', fact.get('value', '')))
            predicate = self.tokens(fact.get('predicate', ''))
            subject = self.tokens(fact.get('subject', ''))
            if not value:
                continue
            for clause in clauses:
                words = self.tokens(clause)
                if not value <= words:
                    continue
                short_answer = not (words - value - filler)
                anchored = profile_query or short_answer or (bool(predicate) and bool(subject)
                                                            and predicate <= words and subject <= words)
                if not anchored:
                    continue
                if words & negatives or re.search(r'نمی[‌\s]+باشد', clause):
                    refuted = True
                else:
                    support = True
        if refuted:
            return "REFUTED", sources
        return ("SUPPORTED" if support else "NOT_ENOUGH_INFO"), sources

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
            if not isinstance(fact, dict) or fact.get('superseded') is True:
                continue
            anchor = self.tokens(str(fact.get('subject','')) + ' ' + str(fact.get('predicate',''))) - operators
            if (anchor and anchor <= question_terms) or (profile_query and fact.get('subject') == 'user'):
                relevant.append(fact)
        evidence_status, evidence_sources = self._grounding(a, relevant, profile_query)
        supported = evidence_status == 'SUPPORTED'
        aligned = bool(question_terms & answer_terms) or supported
        score = .72
        if asks_information and question_terms and not aligned:
            reasons.append('unrelated_answer')
            score = .4
        if evidence_status == 'CONFLICTING':
            contradictions.append('conflicting_evidence')
        elif evidence_status == 'REFUTED':
            contradictions.append('evidence_negated')
        elif relevant and not supported:
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
        return VerificationResult(accepted, score, reasons, contradictions, "PASS" if accepted else "REPAIR", evidence_status, evidence_sources)
