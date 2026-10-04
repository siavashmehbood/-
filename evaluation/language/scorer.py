"""Deterministic first-pass scoring; semantic/blind judges can add evidence later."""
from __future__ import annotations
import re


def _norm(text):
    text = str(text or "").replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    return " ".join(text.casefold().split())


class DeterministicScorer:
    def score(self, case, answer):
        answer_n = _norm(answer)
        expected = [_norm(x) for x in case.expected_facts]
        forbidden = [_norm(x) for x in case.forbidden_claims]
        required_hits = sum(bool(x and x in answer_n) for x in expected)
        forbidden_hits = sum(bool(x and x in answer_n) for x in forbidden)
        if forbidden_hits:
            return {"score": 0.0, "required_hits": required_hits,
                    "forbidden_hits": forbidden_hits, "method": "deterministic"}
        if expected:
            ratio = required_hits / len(expected)
        else:
            ratio = 1.0 if answer_n else 0.0
        return {"score": round(case.max_score * ratio, 4),
                "required_hits": required_hits, "forbidden_hits": 0,
                "method": "deterministic"}
