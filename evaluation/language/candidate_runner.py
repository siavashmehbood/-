"""Comparable candidate execution and promotion decision."""
from __future__ import annotations
from .runner import BenchmarkRunner
from .reports import summarize
from .gap_map import build_gap_map
from .selection_gate import SelectionGate


def evaluate_candidate(engine, cases):
    rows=BenchmarkRunner(engine).run(cases)
    return {"identity":engine.identity,"rows":rows,"summary":summarize(rows)}


def compare_candidates(evaluations):
    rows=[]
    for evaluation in evaluations:
        rows.extend(evaluation["rows"])
    return build_gap_map(rows)


def promotion_decision(candidate_metrics, baseline_metrics=None):
    return SelectionGate().evaluate(candidate_metrics,baseline_metrics)
