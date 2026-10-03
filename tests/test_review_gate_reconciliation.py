"""Crash/restart reconciliation between the reviewer ledger and LearningGate."""
import json

import pytest

from runtime.app import IranRuntime
from security.learning_gate import LearningGate


def runtime_shell(tmp_path):
    runtime = IranRuntime.__new__(IranRuntime)
    runtime.root = tmp_path
    runtime.learning_gate = LearningGate(tmp_path / "data" / "learning_proposals.json")
    return runtime


def add_proposal(runtime, summary):
    return runtime.learning_gate.request(
        "knowledge.add_fact",
        {
            "subject": "reconciliation",
            "predicate": "case",
            "object": summary,
            "confidence": 0.9,
            "source": "fixture",
        },
        summary,
    )


def update_review(tmp_path, proposal_id, **changes):
    path = tmp_path / "data" / "chatgpt_reviews.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    row = next(
        item for item in rows
        if str(item.get("proposal_id")) == str(proposal_id)
    )
    row.update(changes)
    path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_restart_repairs_reviewer_rejection_before_gate_write(tmp_path):
    runtime = runtime_shell(tmp_path)
    proposal = add_proposal(runtime, "reviewer rejection crash")
    proposal_id = proposal["proposal_id"]
    runtime.sync_chatgpt_learning_reviews()
    update_review(
        tmp_path,
        proposal_id,
        review_status="reviewed",
        chatgpt_decision="reject",
        status="rejected",
        reviewed_at="2030-01-01T00:00:00+00:00",
        provider="fixture",
        model="openrouter/free",
    )
    assert runtime.learning_gate.get(proposal_id)["status"] == "pending"

    restarted = runtime_shell(tmp_path)
    restarted.sync_chatgpt_learning_reviews()

    assert restarted.learning_gate.get(proposal_id)["status"] == "rejected"
    assert restarted.human_learning_pending(10) == []
    events = restarted.review_decision_journal_page(limit=10)["items"]
    assert [(event["actor"], event["decision"]) for event in events] == [
        ("reviewer", "reject")
    ]


@pytest.mark.parametrize("terminal_status", ["approved", "rejected"])
def test_restart_backfills_ledger_from_terminal_gate_without_redeciding(
    tmp_path, terminal_status
):
    runtime = runtime_shell(tmp_path)
    proposal = add_proposal(runtime, f"human {terminal_status} crash")
    proposal_id = proposal["proposal_id"]
    runtime.sync_chatgpt_learning_reviews()
    update_review(
        tmp_path,
        proposal_id,
        review_status="reviewed",
        chatgpt_decision="learn",
        status="human_pending",
        reviewed_at="2030-01-01T00:00:00+00:00",
        provider="fixture",
        model="openrouter/free",
    )
    runtime.learning_gate.decide(proposal_id, terminal_status)

    restarted = runtime_shell(tmp_path)
    before = restarted.learning_gate.get(proposal_id)
    restarted.sync_chatgpt_learning_reviews()
    after = restarted.learning_gate.get(proposal_id)

    assert before["status"] == terminal_status
    assert after == before
    path = tmp_path / "data" / "chatgpt_reviews.json"
    row = next(
        item for item in json.loads(path.read_text(encoding="utf-8"))
        if item.get("proposal_id") == proposal_id
    )
    assert row["status"] == terminal_status
    assert row["human_decision"] == terminal_status
    assert row["human_decided_at"] == before["updated_at"]
    assert restarted.human_learning_pending(10) == []
    events = restarted.review_decision_journal_page(limit=10)["items"]
    assert [(event["actor"], event["decision"]) for event in events] == [
        ("human", terminal_status),
        ("reviewer", "learn"),
    ]
