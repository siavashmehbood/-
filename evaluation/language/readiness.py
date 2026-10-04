"""Preflight audit for real local foundation benchmarking."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class Readiness:
    ready: bool
    reasons: tuple[str,...]
    candidates: tuple[str,...]


def audit(root: str|Path) -> Readiness:
    root=Path(root)
    reasons=[]
    candidates_path=root/"evaluation/language/candidates.json"
    plan_path=root/"evaluation/language/experiment_plan.json"
    if not candidates_path.exists(): reasons.append("missing:candidates.json")
    if not plan_path.exists(): reasons.append("missing:experiment_plan.json")
    if reasons: return Readiness(False,tuple(reasons),())
    registry=json.loads(candidates_path.read_text(encoding="utf-8"))
    plan=json.loads(plan_path.read_text(encoding="utf-8"))
    rows=registry.get("candidates",registry if isinstance(registry,list) else [])
    pinned={x["candidate_id"] for x in rows
            if x.get("role")=="foundation_candidate" and x.get("revision") not in ("","UNPINNED",None)}
    experiments=plan.get("experiments",[])
    planned={x.get("candidate_id") for x in experiments}
    if pinned != planned: reasons.append("candidate_plan_mismatch")
    for cid in sorted(pinned):
        rounds={x.get("round") for x in experiments if x.get("candidate_id")==cid}
        if rounds != {"quality_baseline","deployment"}: reasons.append(f"incomplete_rounds:{cid}")
    # GitHub CI deliberately does not download multi-GB model weights. Real benchmark
    # readiness therefore means the protocol is complete, not that measurements exist.
    return Readiness(not reasons,tuple(reasons),tuple(sorted(pinned)))
