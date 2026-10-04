"""Deterministic first-pass scoring; rubric-only cases must be judged, never auto-pass."""
from __future__ import annotations


def _norm(text):
    text=str(text or "").replace("ي","ی").replace("ك","ک").replace("\u200c"," ")
    return " ".join(text.casefold().split())


class DeterministicScorer:
    def score(self,case,answer):
        answer_n=_norm(answer)
        expected=[_norm(x) for x in case.expected_facts]
        forbidden=[_norm(x) for x in case.forbidden_claims]
        required_hits=sum(bool(x and x in answer_n) for x in expected)
        forbidden_hits=sum(bool(x and x in answer_n) for x in forbidden)
        if forbidden_hits:
            return {"score":0.0,"required_hits":required_hits,"forbidden_hits":forbidden_hits,
                    "method":"deterministic","requires_judge":False}
        if expected:
            ratio=required_hits/len(expected)
            return {"score":round(case.max_score*ratio,4),"required_hits":required_hits,
                    "forbidden_hits":0,"method":"deterministic","requires_judge":False}
        # Naturalness/context/style cannot be honestly inferred from non-empty output.
        return {"score":None,"required_hits":0,"forbidden_hits":0,
                "method":"rubric_pending","requires_judge":True}
