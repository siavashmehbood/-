"""Deterministic multi-step symbolic reasoning for IRAN.

The engine separates retrieval, inference, confidence propagation and
realization. It never calls an external model and never treats retrieval as
proof. Verified reasoning episodes are persisted for later strategy learning.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json
import re


@dataclass
class ReasoningStep:
    kind: str
    source: str
    text: str
    confidence: float
    hop: int = 0


@dataclass
class ChainResult:
    status: str
    answer: str
    confidence: float
    steps: list
    assumptions: list
    alternatives: list
    query_units: list

    def as_dict(self):
        return asdict(self)


class ChainReasoner:
    """Local retrieve -> infer -> verify -> realize reasoning engine."""

    STOP = {"و", "در", "از", "به", "که", "را", "برای", "این", "آن", "یک",
            "با", "من", "تو", "ما", "است", "هست", "می", "کن", "کرد", "چی", "چیه",
            "چیست", "چرا", "چطور", "چگونه", "آیا"}

    def __init__(self, knowledge, memory, path):
        self.knowledge = knowledge
        self.memory = memory
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.episodes = self._load()

    def _load(self):
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))[-2000:]
        except Exception:
            return []

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.episodes[-2000:], ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @classmethod
    def tokens(cls, text):
        raw = re.findall(r"[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]*", str(text).lower())
        return {x for x in raw if len(x) > 1 and x not in cls.STOP}

    @classmethod
    def similarity(cls, a, b):
        x, y = cls.tokens(a), cls.tokens(b)
        return len(x & y) / max(1, len(x | y))

    def decompose(self, text):
        t = str(text).strip()
        units = [x.strip() for x in re.split(r"[؟?]", t) if x.strip()]
        if len(units) <= 1:
            pieces = re.split(r"\s+و\s+(?=چرا\b|چطور\b|چگونه\b|آیا\b)", t.rstrip("؟?"))
            if len(pieces) > 1:
                units = [x.strip() for x in pieces if x.strip()]
        return units or ([t] if t else [])

    def _candidate_facts(self, query, limit=20):
        try:
            rows = self.knowledge.query(query, limit)
            if not rows:
                seen = set()
                rows = []
                for token in self.tokens(query):
                    for fact in self.knowledge.query(token, limit):
                        key = (fact.get('subject'), fact.get('predicate'), fact.get('object'))
                        if key not in seen:
                            seen.add(key)
                            rows.append(fact)
        except Exception:
            rows = []
        ranked = []
        for fact in rows:
            text = " ".join(str(fact.get(k, "")) for k in ("subject", "predicate", "object"))
            sim = self.similarity(query, text)
            conf = float(fact.get("confidence", .5))
            if "contradicted_by" in fact:
                conf *= .45
            ranked.append((.55 * sim + .45 * conf, fact))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in ranked[:limit]]

    def _entity_seeds(self, query):
        seeds = []
        try:
            for fact in self.knowledge.query(query, 20):
                if fact.get("subject") not in seeds:
                    seeds.append(fact.get("subject"))
        except Exception:
            pass
        for token in self.tokens(query):
            if token not in seeds:
                try:
                    if self.knowledge.related(token, 1):
                        seeds.append(token)
                except Exception:
                    pass
        return seeds[:8]

    def _infer_paths(self, query, max_hops=3, limit=12):
        paths = []
        for seed in self._entity_seeds(query):
            try:
                inferred = self.knowledge.infer(seed, depth=max_hops, limit=limit)
            except Exception:
                inferred = []
            for item in inferred:
                fact = item.get("fact", {})
                text = f"{fact.get('subject')} {fact.get('predicate')} {fact.get('object')}"
                relevance = self.similarity(query, text)
                score = float(item.get("inferred_confidence", 0)) * (.55 + .45 * relevance)
                paths.append((score, item))
        paths.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in paths[:limit]]

    def _memory_evidence(self, query, limit=6):
        try:
            rows = self.memory.working_context(query, limit)
        except Exception:
            return []
        out = []
        for row in rows:
            text = row[1] if isinstance(row, (tuple, list)) and len(row) > 1 else str(row)
            sim = self.similarity(query, text)
            if sim > .05:
                out.append((sim, str(text)))
        return [x[1] for x in sorted(out, reverse=True)[:limit]]

    def _fact_answer(self, query, facts, paths):
        candidates = []
        for fact in facts:
            obj = str(fact.get("object", "")).strip()
            if not obj:
                continue
            conf = float(fact.get("confidence", .5))
            if "contradicted_by" in fact:
                conf *= .45
            candidates.append((conf, fact, 1))
        for item in paths:
            fact = item.get("fact", {})
            obj = str(fact.get("object", "")).strip()
            if obj:
                candidates.append((float(item.get("inferred_confidence", .3)), fact, int(item.get("hop", 1))))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        score, fact, hop = candidates[0]
        obj = str(fact.get("object", "")).strip()
        subject = str(fact.get("subject", "")).strip()
        predicate = str(fact.get("predicate", "")).strip()
        if hop > 1:
            answer = f"بر اساس زنجیره دانش محلی، {subject} با رابطه «{predicate}» به «{obj}» می‌رسد."
        else:
            answer = f"{obj} است."
        return answer, score, fact, hop

    def reason(self, text, min_confidence=.72):
        units = self.decompose(text)
        all_steps = []
        answers = []
        confidences = []
        assumptions = []
        alternatives = []
        for unit in units:
            facts = self._candidate_facts(unit)
            paths = self._infer_paths(unit)
            for fact in facts[:5]:
                all_steps.append(ReasoningStep("retrieve", str(fact.get("source", "local")),
                    f"{fact.get('subject')} | {fact.get('predicate')} | {fact.get('object')}",
                    float(fact.get("confidence", .5)), 1))
            for item in paths[:5]:
                fact = item.get("fact", {})
                all_steps.append(ReasoningStep("infer", str(fact.get("source", "local")),
                    f"{fact.get('subject')} | {fact.get('predicate')} | {fact.get('object')}",
                    float(item.get("inferred_confidence", .3)), int(item.get("hop", 1))))
            result = self._fact_answer(unit, facts, paths)
            if result:
                answer, score, fact, hop = result
                if score >= min_confidence:
                    answers.append(answer)
                    confidences.append(score)
                else:
                    assumptions.append(f"شواهد برای «{unit}» اطمینان کافی ندارند")
            else:
                assumptions.append(f"برای «{unit}» واقعیت محلی پیدا نشد")
        if not answers:
            return ChainResult("UNKNOWN", "", 0.0, [asdict(x) for x in all_steps], assumptions, alternatives, units)
        confidence = min(confidences) if len(confidences) > 1 else confidences[0]
        status = "PARTIAL" if len(answers) < len(units) else "VERIFIED_CANDIDATE"
        return ChainResult(status, "\n".join(f"{i+1}) {x}" for i, x in enumerate(answers)),
                           round(min(0.99, confidence), 3), [asdict(x) for x in all_steps],
                           assumptions, alternatives, units)

    def record(self, query, result, accepted=False, score=None):
        if not result:
            return
        row = {"query": str(query), "status": result.status, "confidence": result.confidence,
               "accepted": bool(accepted), "score": float(score if score is not None else result.confidence),
               "steps": result.steps[:20], "time": datetime.now().isoformat(timespec="seconds")}
        self.episodes.append(row)
        self.episodes = self.episodes[-2000:]
        self._save()

    def strategy(self, query):
        """Choose reasoning depth from verified local experience, not a fixed guess."""
        related = [x for x in self.episodes if self.similarity(query, x.get("query", "")) >= .18]
        if not related:
            return {"depth": 2, "confidence": .35, "samples": 0}
        good = [x for x in related if x.get("accepted") and float(x.get("score", 0)) >= .75]
        depth = 3 if any(any(int(s.get("hop", 0)) >= 2 for s in x.get("steps", [])) for x in good) else 2
        conf = min(.9, .35 + .06 * len(good))
        return {"depth": depth, "confidence": round(conf, 3), "samples": len(related)}
