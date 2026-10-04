"""Blind rubric score application with provenance; no mandatory cloud judge."""
from __future__ import annotations


def apply_judgments(rows, judgments):
    """Apply externally produced blind scores by case_id.

    judgments: {case_id: {"score": 0..100, "judge": "...", "reason": "..."}}
    The candidate model identity need not be exposed to the judge.
    """
    output=[]
    for row in rows:
        item=dict(row)
        if item.get("score") is None and item["case_id"] in judgments:
            judgment=judgments[item["case_id"]]
            score=float(judgment["score"])
            if not 0 <= score <= 100: raise ValueError("judge score must be 0..100")
            item["score"]=score
            item["judgment"]={"judge":str(judgment.get("judge","blind")),
                              "reason":str(judgment.get("reason",""))}
        output.append(item)
    return output
