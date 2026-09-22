"""Deterministic Memory Intelligence v2 for the local IRAN architecture."""
from dataclasses import dataclass, asdict
from datetime import datetime
import math
import re


@dataclass
class MemoryCandidate:
    kind: str
    content: str
    created_at: str = ""
    confidence: float = 0.5
    importance: float = 0.5
    relevance: float = 0.0
    freshness: float = 0.0
    status: str = "active"
    source: str = "local"
    score: float = 0.0
    reason: str = ""

    def to_dict(self):
        return asdict(self)


class MemoryIntelligence:
    """Selects memories by relevance, freshness, confidence and outcome state."""
    STOP = {
        "این", "آن", "اون", "همین", "همون", "برای", "درباره", "چی", "چیه",
        "چیست", "گفتیم", "بگو", "من", "تو", "ما", "را", "رو", "به", "از",
        "در", "که", "و", "با", "است", "هست", "بود", "شد", "می", "شود",
    }

    def __init__(self, memory):
        self.memory = memory

    def _norm(self, text):
        return re.sub(r"\s+", " ", str(text).strip().replace("ي", "ی").replace("ك", "ک"))

    def _tokens(self, text):
        return {x for x in re.findall(r"[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]*", self._norm(text).lower()) if x not in self.STOP}

    def _similarity(self, query, content):
        q, c = self._tokens(query), self._tokens(content)
        if not q or not c:
            return 0.0
        overlap = len(q & c) / max(1, len(q))
        coverage = len(q & c) / max(1, len(c))
        phrase = 1.0 if self._norm(query).lower() in self._norm(content).lower() else 0.0
        return min(1.0, .62 * overlap + .18 * coverage + .20 * phrase)

    @staticmethod
    def _freshness(created_at, half_life_days=45):
        try:
            age = max(0.0, (datetime.now() - datetime.fromisoformat(created_at)).total_seconds() / 86400)
        except Exception:
            age = 3650.0
        return math.exp(-age / max(1.0, float(half_life_days)))

    def _outcome_status(self, content, state=None, kind=""):
        if not state:
            return "active"
        normalized = self._norm(content)
        if kind == "rejected_answer":
            return "rejected"
        if kind == "accepted_answer":
            return "accepted"
        rejected = {self._norm(x) for x in getattr(state, "rejected_answers", [])}
        accepted = {self._norm(x) for x in getattr(state, "accepted_answers", [])}
        if normalized in rejected:
            return "rejected"
        if normalized in accepted:
            return "accepted"
        corrections = [self._norm(x) for x in getattr(state, "corrections", [])]
        if corrections and normalized and any(normalized in c or c in normalized for c in corrections):
            return "superseded"
        return "active"

    def retrieve(self, query, state=None, limit=8, min_score=0.0):
        """Return ranked, outcome-aware candidates; rejected memories are excluded."""
        q = self._norm(query)
        rows = self.memory.search(q, max(20, int(limit) * 5))
        # Lexical stores can miss Persian follow-ups whose query is mostly a
        # reference (قبلی/همان/ادامه). In that case recent durable context is
        # the relevant retrieval pool, not an empty search result.
        reference_query = bool(re.search(r'\b(قبلی|همان|همون|این|اون|ادامه|قبل)\b', q))
        if reference_query:
            seen = {(row[0], row[1]) for row in rows if isinstance(row, (tuple, list)) and len(row) >= 2}
            for row in self.memory.recent(max(20, int(limit) * 5)):
                if isinstance(row, (tuple, list)) and len(row) >= 3 and (row[0], row[1]) not in seen:
                    rows.append(row[:3]); seen.add((row[0], row[1]))
        candidates = []
        for kind, content, created_at in rows:
            status = self._outcome_status(content, state, kind)
            if status == "rejected":
                continue
            relevance = self._similarity(q, content)
            if reference_query and kind in {"user", "accepted_answer"}:
                relevance = max(relevance, .45)
            freshness = self._freshness(created_at)
            meta = self.memory.conn.execute(
                "SELECT importance,confidence,source FROM memories WHERE kind=? AND content=? LIMIT 1",
                (kind, content),
            ).fetchone()
            importance, confidence, source = meta or (.5, .5, "local")
            status_bonus = {"accepted": .10, "active": .0, "superseded": -.18}.get(status, 0.0)
            score = (.52 * relevance + .18 * freshness + .16 * float(confidence)
                     + .09 * float(importance) + status_bonus)
            if score < float(min_score):
                continue
            reason = f"relevance={relevance:.2f}; freshness={freshness:.2f}; confidence={float(confidence):.2f}; status={status}"
            candidates.append(MemoryCandidate(kind, content, created_at, float(confidence),
                                              float(importance), relevance, freshness, status,
                                              str(source), round(score, 4), reason))
        # Semantic facts and procedural lessons are durable memory layers too.
        for fact in self.memory.semantic_search(q, max(4, int(limit))):
            content = f"{fact.get('subject','')}: {fact.get('predicate','')} = {fact.get('value','')}"
            relevance = self._similarity(q, content)
            score = .68 * relevance + .32 * float(fact.get('confidence', .5))
            candidates.append(MemoryCandidate(
                "semantic_fact", content, fact.get("updated_at", ""),
                float(fact.get("confidence", .5)), .75, relevance,
                self._freshness(fact.get("updated_at", "")), "active",
                str(fact.get("source", "local")), round(score, 4),
                f"semantic relevance={relevance:.2f}; confidence={float(fact.get('confidence', .5)):.2f}",
            ))
        candidates.sort(key=lambda x: (x.score, x.relevance, x.freshness), reverse=True)
        return candidates[:int(limit)]

    def build_context(self, query, state=None, limit=8):
        candidates = self.retrieve(query, state, limit)
        return {
            "query": self._norm(query),
            "count": len(candidates),
            "candidates": [x.to_dict() for x in candidates],
            "selected": [x.to_dict() for x in candidates if x.score >= .42][:int(limit)],
        }

    def record_outcome(self, answer, accepted, state=None):
        """Persist outcome without creating duplicate memories."""
        text = self._norm(answer)
        if not text:
            return {"status": "ignored"}
        if accepted:
            self.memory.add("accepted_answer", text, .86, confidence=.92, source="memory-intelligence")
            return {"status": "accepted", "content": text}
        self.memory.add("rejected_answer", text, .84, confidence=.95, source="memory-intelligence")
        return {"status": "rejected", "content": text}

    def stats(self):
        rows = self.memory.conn.execute(
            "SELECT kind,COUNT(*) FROM memories WHERE kind IN ('accepted_answer','rejected_answer') GROUP BY kind"
        ).fetchall()
        return {kind: count for kind, count in rows}
