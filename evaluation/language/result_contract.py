"""Strict evidence contract for importing real model benchmark measurements."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

REQUIRED_GATE=("persian","multilingual_average","language_minimum","multilingual_loss",
               "critical_language_loss","capability_loss","iran_regressions",
               "one_brain","offline","hidden_gate")
REQUIRED_DEPLOYMENT=("first_token_ms","total_latency_ms","tokens_per_second",
                     "peak_ram_mb","context_tokens","cpu_fallback")


def validate_result(row: Mapping[str,object]):
    missing=[k for k in ("candidate_id","model_id","revision","round","gate_metrics",
                         "quality_metrics","deployment","provenance") if k not in row]
    if missing: raise ValueError("missing result fields: "+",".join(missing))
    if row["round"] not in ("quality_baseline","deployment"):
        raise ValueError("invalid benchmark round")
    provenance=row["provenance"]
    for key in ("runtime","hardware","quantization","timestamp","dataset_fingerprint"):
        if not provenance.get(key): raise ValueError("missing provenance:"+key)
    gate=row["gate_metrics"]
    absent=[k for k in REQUIRED_GATE if k not in gate]
    if absent: raise ValueError("missing gate metrics: "+",".join(absent))
    deployment=row["deployment"]
    absent=[k for k in REQUIRED_DEPLOYMENT if k not in deployment]
    if absent: raise ValueError("missing deployment metrics: "+",".join(absent))
    if not row["quality_metrics"]: raise ValueError("quality metrics cannot be empty")
    return True


def validate_pair(rows):
    rows=list(rows)
    for row in rows: validate_result(row)
    by_candidate={}
    for row in rows: by_candidate.setdefault(row["candidate_id"],set()).add(row["round"])
    incomplete={k:v for k,v in by_candidate.items() if v != {"quality_baseline","deployment"}}
    if incomplete: raise ValueError("candidate missing required round")
    return True
