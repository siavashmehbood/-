"""JSON/JSONL benchmark loading with validation and split isolation."""
from __future__ import annotations
import json
from pathlib import Path
from .schema import BenchmarkCase


def _case(row):
    return BenchmarkCase(
        case_id=str(row["id"]), language=str(row["language"]), tier=str(row["tier"]),
        category=str(row["category"]), difficulty=str(row["difficulty"]),
        messages=tuple(row["messages"]), rubric=tuple(row.get("rubric", ())),
        expected_facts=tuple(row.get("expected_facts", ())),
        forbidden_claims=tuple(row.get("forbidden_claims", ())),
        scoring_method=str(row.get("scoring_method", "rubric")),
        max_score=float(row.get("max_score", 100.0)),
    ).validate()


def load_dataset(path):
    path = Path(path)
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data["cases"] if isinstance(data, dict) else data
    cases = [_case(row) for row in rows]
    ids = [x.case_id for x in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate benchmark case id")
    return cases


def assert_disjoint_splits(*splits):
    seen = set()
    for name, cases in splits:
        ids = {case.case_id for case in cases}
        overlap = seen & ids
        if overlap:
            raise ValueError(f"benchmark leakage in {name}: {sorted(overlap)[:5]}")
        seen |= ids
    return True
