"""Deterministic local self-correction memory for IRAN.

Turns explicit feedback/corrections into durable, query-linked evidence that
can change future response strategy. No model, network or external service.
"""
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import json
import re


@dataclass
class CorrectionRecord:
    question: str
    answer: str
    feedback: str
    kind: str
    correction: str = ""
    lesson: str = ""
    timestamp: str = ""
    uses: int = 0


class SelfCorrectionEngine:
    """Persistent error/feedback ledger with deterministic retrieval."""

    NEGATIVE = ("اشتباه", "غلط", "بد بود", "ضعیف", "نه", "wrong", "bad", "incorrect")
    POSITIVE = ("درست بود", "درسته", "عالی بود", "خوبه", "correct", "good")

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records = []
        self._load()

    @staticmethod
    def clean(text):
        return re.sub(r"\s+", " ", str(text or "").strip().replace("ي", "ی").replace("ك", "ک"))

    @classmethod
    def tokens(cls, text):
        return set(re.findall(r"[\wآ-ی]+", cls.clean(text).lower()))

    @classmethod
    def similarity(cls, a, b):
        x, y = cls.tokens(a), cls.tokens(b)
        return len(x & y) / max(1, len(x | y))

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.records = data[-2000:] if isinstance(data, list) else []
        except (OSError, ValueError, TypeError):
            self.records = []

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.records[-2000:], ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @classmethod
    def classify_feedback(cls, text):
        t = cls.clean(text).lower()
        if any(x in t for x in cls.NEGATIVE):
            return "negative"
        if any(x in t for x in cls.POSITIVE):
            return "positive"
        return "neutral"

    @classmethod
    def extract_correction(cls, text):
        t = cls.clean(text)
        patterns = (
            r"^(?:نه[،,]?|اشتباهه[،,]?|اشتباه است[،,]?|غلطه[،,]?|غلط است[،,]?)\s*(.+)$",
            r"^منظورم\s+(.+?)\s+(?:بود|است)$",
        )
        for pattern in patterns:
            match = re.match(pattern, t, re.I)
            if match:
                value = cls.clean(match.group(1)).strip(" ،,:؛")
                if value:
                    return value
        return ""

    def record_feedback(self, question, answer, feedback):
        kind = self.classify_feedback(feedback)
        if kind == "neutral":
            return {"recorded": False, "kind": kind}
        lesson = (
            "retain the response strategy and verify future outcomes"
            if kind == "positive" else
            "do not repeat the rejected response; increase evidence and verify before reuse"
        )
        row = CorrectionRecord(
            self.clean(question), self.clean(answer), self.clean(feedback), kind,
            "", lesson, datetime.now().isoformat(timespec="seconds"), 0,
        )
        self.records.append(asdict(row))
        self._save()
        return {"recorded": True, "kind": kind, "lesson": lesson}

    def record_correction(self, question, answer, correction, lesson=""):
        value = self.extract_correction(correction) or self.clean(correction)
        row = CorrectionRecord(
            self.clean(question), self.clean(answer), self.clean(correction), "correction",
            value, lesson or "use the corrected interpretation and verify it on the next related turn",
            datetime.now().isoformat(timespec="seconds"), 0,
        )
        self.records.append(asdict(row))
        self._save()
        return {"recorded": True, "kind": "correction", "correction": value, "lesson": row.lesson}

    def retrieve(self, query, limit=5, threshold=.10):
        q = self.clean(query)
        ranked = []
        for row in self.records:
            score = max(
                self.similarity(q, row.get("question", "")),
                self.similarity(q, row.get("correction", "")) * .9,
                self.similarity(q, row.get("feedback", "")) * .65,
            )
            if score < threshold:
                continue
            recency = 1.0 if row.get("timestamp", "") else .5
            ranked.append((score * .82 + recency * .03 + min(.15, int(row.get("uses", 0)) * .02), row))
        ranked.sort(key=lambda x: x[0], reverse=True)
        selected = []
        for score, row in ranked[:int(limit)]:
            row = dict(row)
            row["question_match"] = round(self.similarity(q, row.get("question", "")), 4)
            row["correction_match"] = round(self.similarity(q, row.get("correction", "")), 4)
            row["match_score"] = round(score, 4)
            selected.append(row)
        return selected

    def recommend(self, query, limit=5):
        rows = self.retrieve(query, limit)
        for row in rows:
            row["uses"] = int(row.get("uses", 0)) + 1
        if rows:
            self._save()
        return rows

    def strongest(self, query):
        rows = self.retrieve(query, 5)
        return rows[0] if rows else None

    def should_avoid(self, query, answer):
        answer = self.clean(answer)
        for row in self.retrieve(query, 8):
            if row.get("kind") not in {"negative", "correction"}:
                continue
            if float(row.get("question_match", 0)) < .88:
                continue
            rejected = row.get("answer", "")
            if rejected and self.similarity(answer, rejected) >= .72:
                return True
        return False

    def stats(self):
        return {
            "records": len(self.records),
            "negative": sum(r.get("kind") == "negative" for r in self.records),
            "positive": sum(r.get("kind") == "positive" for r in self.records),
            "corrections": sum(r.get("kind") == "correction" for r in self.records),
        }
