import pytest
from self.cognitive_growth import CapabilityBenchmark, CognitiveGrowthCycle, WeaknessLedger


def test_failure_creates_structured_persistent_weakness_and_mission(tmp_path):
    cycle = CognitiveGrowthCycle(tmp_path)
    out = cycle.evaluate_failure(
        "learned knowledge transfer", "unseen-b", "expected learned fact",
        "UNKNOWN", "approved knowledge was not retrieved", ["trace:unseen-b"], .9)
    w = out["weakness"]
    required = {
        "weakness_id","capability","failed_task","expected_result","actual_result",
        "failure_reason","confidence","recurrence_count","evidence","related_components",
        "related_knowledge","related_skills","proposed_learning_goal","status",
    }
    assert required.issubset(w)
    assert out["mission"]["weakness_id"] == w["weakness_id"]
    assert out["mission"]["requires_reviewer"] is True
    assert out["mission"]["requires_human_approval"] is True
    restored = WeaknessLedger(tmp_path / "data" / "weaknesses.json")
    assert restored.rows[0]["weakness_id"] == w["weakness_id"]


def test_repeated_failure_increments_recurrence_instead_of_duplicate(tmp_path):
    ledger = WeaknessLedger(tmp_path / "weaknesses.json")
    kwargs = dict(capability="reasoning", failed_task="case-x", expected_result="42",
                  actual_result="unknown", failure_reason="missing inference",
                  confidence=.8, evidence=["case-x"], proposed_learning_goal="infer")
    first = ledger.record(**kwargs)
    second = ledger.record(**kwargs)
    assert first["weakness_id"] == second["weakness_id"]
    assert second["recurrence_count"] == 2
    assert len(ledger.rows) == 1


def test_no_improvement_never_becomes_mastery_and_requests_remediation(tmp_path):
    bench = CapabilityBenchmark(tmp_path / "bench.json")
    cases = [{"case_id":"u1","input":"a","expected":"x"}, {"case_id":"u2","input":"b","expected":"y"}]
    evaluate = lambda output, case: output == case["expected"]
    before = bench.run("transfer", cases, lambda _: "wrong", evaluate, "baseline")
    after = bench.run("transfer", cases, lambda _: "wrong", evaluate, "post_learning")
    result = bench.compare(before, after)
    assert result["delta"] == 0
    assert result["mastery_eligible"] is False
    assert result["next"] == "remediate"


def test_real_unseen_improvement_is_measured_and_survives_restart(tmp_path):
    train_examples = {"train-a": "rule"}  # deliberately not benchmark inputs
    cases = [
        {"case_id":"unseen-1","input":"different wording one","expected":"rule"},
        {"case_id":"unseen-2","input":"different context two","expected":"rule"},
        {"case_id":"unseen-3","input":"novel transfer three","expected":"rule"},
    ]
    evaluate = lambda output, case: output == case["expected"]
    bench = CapabilityBenchmark(tmp_path / "bench.json")
    before = bench.run("learned skill transfer", cases, lambda _: "UNKNOWN", evaluate, "baseline")

    # This stands for an already-reviewed and explicitly human-approved durable skill.
    # Governance itself is tested end-to-end in test_candidate_gate_order.py; this test
    # proves that evaluation uses unseen cases and that the durable capability changes behavior.
    approved_skill_path = tmp_path / "approved_skill.txt"
    approved_skill_path.write_text(train_examples["train-a"], encoding="utf-8")

    def learned_solver(_):
        return approved_skill_path.read_text(encoding="utf-8")

    after = bench.run("learned skill transfer", cases, learned_solver, evaluate, "post_learning")
    comparison = bench.compare(before, after)
    assert comparison == {
        "capability":"learned skill transfer","before":0,"after":3,"total":3,
        "delta":3,"improved":True,"mastery_eligible":True,"next":"keep",
    }

    restarted = CapabilityBenchmark(tmp_path / "bench.json")
    restart = restarted.run("learned skill transfer", cases, learned_solver, evaluate, "restart")
    assert restart["score"] == 3
    assert len(restarted.state["runs"]) == 3


def test_growth_cycle_requires_learning_and_retest_before_conclusion(tmp_path):
    cycle = CognitiveGrowthCycle(tmp_path)
    failure = cycle.evaluate_failure("planning", "u", "plan", "none", "no decomposition")
    wid = failure["weakness"]["weakness_id"]
    cases = [{"case_id":"p1","input":"u"}]
    before = cycle.benchmark.run("planning", cases, lambda _: False, bool, "baseline")
    after = cycle.benchmark.run("planning", cases, lambda _: True, bool, "post_learning")

    with pytest.raises(ValueError, match="retest"):
        cycle.conclude(wid, before, after)
    assert cycle.begin_learning(wid)["status"] == "learning"
    assert cycle.begin_retest(wid)["status"] == "retest"
    out = cycle.conclude(wid, before, after)
    assert out["weakness_status"] == "resolved"


def test_growth_cycle_no_improvement_returns_to_remediation(tmp_path):
    cycle = CognitiveGrowthCycle(tmp_path)
    failure = cycle.evaluate_failure("planning", "flat", "plan", "none", "no decomposition")
    wid = failure["weakness"]["weakness_id"]
    cases = [{"case_id":"p1","input":"flat"}]
    before = cycle.benchmark.run("planning", cases, lambda _: False, bool, "baseline")
    flat = cycle.benchmark.run("planning", cases, lambda _: False, bool, "post_learning")
    cycle.begin_learning(wid)
    cycle.begin_retest(wid)
    out = cycle.conclude(wid, before, flat)
    assert out["weakness_status"] == "remediation"


def test_benchmark_rejects_case_identity_drift(tmp_path):
    bench = CapabilityBenchmark(tmp_path / "bench.json")
    before = bench.run("planning", [{"case_id":"a","input":"x"}], lambda x: False,
                       lambda output, case: bool(output), "baseline")
    after = bench.run("planning", [{"case_id":"b","input":"y"}], lambda x: True,
                      lambda output, case: bool(output), "post_learning")
    with pytest.raises(ValueError, match="case identity mismatch"):
        bench.compare(before, after)
