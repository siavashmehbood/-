"""Reproducible two-round foundation experiment manifest and result validation."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping, Sequence

ROUNDS=("quality_baseline","deployment")


@dataclass(frozen=True)
class ExperimentSpec:
    candidate_id: str
    model_id: str
    revision: str
    round: str
    quantization: str
    context_length: int
    temperature: float = 0.2
    max_tokens: int = 512
    seed: int = 0
    runtime: str = ""
    hardware: Mapping[str, object] = field(default_factory=dict)

    def validate(self):
        if self.round not in ROUNDS: raise ValueError("unknown experiment round")
        if not self.candidate_id or not self.model_id or not self.revision:
            raise ValueError("candidate/model/revision must be pinned")
        if self.revision=="UNPINNED": raise ValueError("revision must be pinned")
        if self.context_length <= 0: raise ValueError("context_length must be positive")
        return self


def validate_comparison(specs: Sequence[ExperimentSpec]):
    specs=[x.validate() for x in specs]
    candidates={x.candidate_id for x in specs}
    rounds={x.round for x in specs}
    missing={c: set(ROUNDS)-{x.round for x in specs if x.candidate_id==c} for c in candidates}
    missing={k:sorted(v) for k,v in missing.items() if v}
    if missing: raise ValueError(f"missing experiment rounds: {missing}")
    quality=[x for x in specs if x.round=="quality_baseline"]
    if len({(x.temperature,x.max_tokens) for x in quality}) != 1:
        raise ValueError("quality baseline generation settings must match")
    return {"candidates":sorted(candidates),"rounds":sorted(rounds)}
