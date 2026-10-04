"""Load researched candidate metadata without importing model frameworks."""
from __future__ import annotations
import json
from pathlib import Path
from language_engine.candidates import CandidateManifest


def load_registry(path=None):
    path=Path(path or Path(__file__).with_name("candidates.json"))
    return json.loads(path.read_text(encoding="utf-8"))


def eligible_foundations(registry=None):
    data=registry or load_registry()
    result=[]
    for row in data["candidates"]:
        if row.get("role")!="foundation_candidate": continue
        if row.get("revision")=="UNPINNED": continue
        item=CandidateManifest(
            candidate_id=row["candidate_id"],family=row["family"],model_id=row["model_id"],
            revision=row["revision"],license_id=row["license_id"],
            context_length=int(row.get("context_length",0)),local_capable=bool(row.get("local_capable")),
            metadata={"role":row["role"],"source":row.get("source","")}
        ).validate()
        result.append(item)
    return result
