"""Machine-readable benchmark report construction."""
from __future__ import annotations
from collections import defaultdict


def summarize(rows):
    by_language=defaultdict(list); by_category=defaultdict(list)
    for row in rows:
        by_language[row["language"]].append(float(row["score"]))
        by_category[row["category"]].append(float(row["score"]))
    avg=lambda values: round(sum(values)/len(values),4) if values else 0.0
    return {
        "cases":len(rows),
        "overall":avg([float(x["score"]) for x in rows]),
        "languages":{k:avg(v) for k,v in sorted(by_language.items())},
        "categories":{k:avg(v) for k,v in sorted(by_category.items())},
        "latency_ms":{"average":avg([float(x.get("latency_ms",0)) for x in rows])},
    }
