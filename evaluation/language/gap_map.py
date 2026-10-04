"""Aggregate only judged comparable results into capability/language gaps."""
from __future__ import annotations
from collections import defaultdict


def build_gap_map(rows):
    buckets=defaultdict(lambda:defaultdict(list))
    for row in rows:
        if row.get("score") is None: continue
        buckets[f'{row["language"]}:{row["category"]}'][str(row["model"])].append(float(row["score"]))
    output={}
    for key,models in sorted(buckets.items()):
        means={model:round(sum(scores)/len(scores),4) for model,scores in models.items() if scores}
        best=max(means.values()) if means else 0.0
        winners=sorted(model for model,value in means.items() if value==best)
        output[key]={"scores":means,"winners":winners,"all_weak":bool(means) and best<60.0}
    return output
