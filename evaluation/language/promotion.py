"""Final promotion requires complete evidence; absence is BLOCKED, never a guessed winner."""
from __future__ import annotations
from .selection_gate import SelectionGate
from .selection_score import weighted_score


def select_foundation(records):
    evaluated=[]
    for row in records:
        missing=[k for k in ("candidate_id","gate_metrics","quality_metrics","deployment") if k not in row]
        if missing:
            evaluated.append({"candidate_id":row.get("candidate_id","unknown"),"status":"BLOCKED",
                              "reasons":["missing:"+",".join(missing)]})
            continue
        gate=SelectionGate().evaluate(row["gate_metrics"],row.get("baseline_metrics"))
        deployment=row["deployment"]
        reasons=list(gate["reasons"])
        if not deployment.get("passed",False): reasons += ["deployment:"+x for x in deployment.get("reasons",["failed"])]
        if reasons:
            evaluated.append({"candidate_id":row["candidate_id"],"status":"REJECT","reasons":reasons})
        else:
            evaluated.append({"candidate_id":row["candidate_id"],"status":"ELIGIBLE",
                              "score":weighted_score(row["quality_metrics"]),"reasons":[]})
    winners=sorted((x for x in evaluated if x["status"]=="ELIGIBLE"),
                   key=lambda x:(-x["score"],x["candidate_id"]))
    return {"selected":winners[0]["candidate_id"] if winners else None,
            "status":"SELECTED" if winners else "BLOCKED","evaluated":evaluated}
