"""Weighted ranking after hard gates pass.

Hard gates always dominate this score; this number cannot rescue a failed candidate.
"""
from __future__ import annotations

WEIGHTS={"persian":.45,"multilingual":.20,"reasoning_knowledge":.12,
         "context_instruction":.08,"code":.05,"tool_agent":.05,"safety":.05}


def weighted_score(metrics):
    missing=[key for key in WEIGHTS if key not in metrics]
    if missing: raise ValueError("missing weighted metrics: "+",".join(missing))
    return round(sum(float(metrics[key])*weight for key,weight in WEIGHTS.items()),4)


def rank_eligible(candidates,gate):
    eligible=[]
    for row in candidates:
        decision=gate.evaluate(row["gate_metrics"],row.get("baseline_metrics"))
        if decision["passed"]:
            eligible.append((weighted_score(row["quality_metrics"]),row["candidate_id"]))
    return sorted(eligible,key=lambda item:(-item[0],item[1]))
