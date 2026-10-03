"""Runtime decision-event synchronization tests for the review journal."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

from runtime.app import IranRuntime


def runtime_shell(tmp_path):
    runtime = IranRuntime.__new__(IranRuntime)
    runtime.root = tmp_path
    return runtime


def write_reviews(tmp_path, rows):
    path = tmp_path / "data" / "chatgpt_reviews.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def reviewed_row(proposal_id="proposal-a"):
    return {
        "proposal_id": proposal_id,
        "review_status": "reviewed",
        "chatgpt_decision": "learn",
        "reviewed_at": "2030-01-01T00:00:00+00:00",
        "provider": "fixture",
        "model": "openrouter/free",
        "status": "human_pending",
        "source": "learning_gate",
        "payload": {},
    }


def test_reviewer_decision_is_journaled_without_human_gate_bypass(tmp_path):
    row = reviewed_row()
    write_reviews(tmp_path, [row])
    runtime = runtime_shell(tmp_path)
    runtime.sync_chatgpt_learning_reviews = Mock(
        return_value={"created": 0, "total": 1, "not_reviewed": 0, "reviewed": 1}
    )
    runtime.chatgpt_review_worker = SimpleNamespace(
        process_one=lambda: {
            "ok": True,
            "reason": "reviewed",
            "proposal_id": row["proposal_id"],
            "learn": True,
        }
    )
    runtime.chatgpt_learning_review_status = lambda proposal_id: {
        "exists": True,
        "reviewed": True,
        "row": dict(row),
    }
    runtime.learning_gate = SimpleNamespace(decide=Mock())
    runtime.learning_missions = SimpleNamespace(mark_review=Mock())

    result = runtime.process_one_chatgpt_learning_review()
    page = runtime.review_decision_journal_page(limit=10)

    assert result["learn"] is True
    assert [(event["actor"], event["decision"]) for event in page["items"]] == [
        ("reviewer", "learn")
    ]
    runtime.learning_gate.decide.assert_not_called()


def test_human_decision_sync_appends_after_reviewer_event(tmp_path):
    row = reviewed_row()
    path = write_reviews(tmp_path, [row])
    runtime = runtime_shell(tmp_path)

    assert runtime._set_human_review_status(
        row["proposal_id"], "approved", "gate-a", "explicit-test"
    )

    page = runtime.review_decision_journal_page(limit=10)
    assert [(event["actor"], event["decision"]) for event in page["items"]] == [
        ("human", "approved"),
        ("reviewer", "learn"),
    ]
    stored = json.loads(path.read_text(encoding="utf-8"))[0]
    assert stored["gate_proposal_id"] == "gate-a"
    assert stored["human_source"] == "explicit-test"


def test_restart_rebuilds_missing_events_once_without_touching_gate(tmp_path):
    row = reviewed_row()
    row.update({
        "human_decision": "rejected",
        "human_decided_at": "2030-01-01T00:01:00+00:00",
        "status": "rejected",
    })
    write_reviews(tmp_path, [row])
    journal_path = tmp_path / "data" / "review_decision_journal.json"
    assert not journal_path.exists()

    restarted = runtime_shell(tmp_path)
    restarted.learning_gate = SimpleNamespace(decide=Mock())
    first = restarted._sync_review_decision_journal()

    restarted_again = runtime_shell(tmp_path)
    restarted_again.learning_gate = SimpleNamespace(decide=Mock())
    second = restarted_again._sync_review_decision_journal()

    assert first["appended"] == 2
    assert second["appended"] == 0
    assert second["count"] == 2
    restarted.learning_gate.decide.assert_not_called()
    restarted_again.learning_gate.decide.assert_not_called()
