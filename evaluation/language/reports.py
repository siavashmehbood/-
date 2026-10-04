"""Machine-readable reports that never hide unjudged cases in an average."""
from __future__ import annotations
from collections import defaultdict


def summarize(rows):
    by_language=defaultdict(list); by_category=defaultdict(list)
    judged=[]
    for row in rows:
        if row.get("score") is None: continue
        value=float(row["score"]); judged.append(value)
        by_language[row["language"]].append(value); by_category[row["category"]].append(value)
    avg=lambda values: round(sum(values)/len(values),4) if values else None
    return {"cases":len(rows),"judged_cases":len(judged),"pending_judge":len(rows)-len(judged),
            "overall":avg(judged),
            "languages":{k:avg(v) for k,v in sorted(by_language.items())},
            "categories":{k:avg(v) for k,v in sorted(by_category.items())},
            "latency_ms":{"average":avg([float(x.get("latency_ms",0)) for x in rows])}}
