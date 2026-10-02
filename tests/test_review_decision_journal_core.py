"""Core tests for the observational reviewer/human decision journal."""
import json
from unittest.mock import patch

import pytest

from persistence import StateCorruptionError
from security.review_decision_journal import ReviewDecisionJournal


def review_row(proposal_id, *, reviewer="learn", human=None):
    row = {
        "proposal_id": proposal_id,
        "review_status": "reviewed",
        "chatgpt_decision": reviewer,
        "reviewed_at": "2030-01-01T00:00:00+00:00",
        "provider": "fixture",
        "model": "openrouter/free",
    }
    if human is not None:
        row["human_decision"] = human
        row["human_decided_at"] = "2030-01-01T00:01:00+00:00"
    return row


def test_sync_builds_hash_chain_and_is_idempotent(tmp_path):
    path = tmp_path / "review_decision_journal.json"
    journal = ReviewDecisionJournal(path)
    rows = [review_row("proposal-a", human="approved")]

    first = journal.sync(rows)
    second = journal.sync(rows)
    events = json.loads(path.read_text(encoding="utf-8"))

    assert first["appended"] == 2
    assert second["appended"] == 0
    assert [event["actor"] for event in events] == ["reviewer", "human"]
    assert [event["decision"] for event in events] == ["learn", "approved"]
    assert events[1]["previous_hash"] == events[0]["event_hash"]
    assert journal.status()["count"] == 2


def test_conflicting_decision_and_tampering_fail_closed(tmp_path):
    path = tmp_path / "review_decision_journal.json"
    journal = ReviewDecisionJournal(path)
    journal.sync([review_row("proposal-a", reviewer="learn")])

    with pytest.raises(StateCorruptionError):
        journal.sync([review_row("proposal-a", reviewer="reject")])

    events = json.loads(path.read_text(encoding="utf-8"))
    events[0]["decision"] = "reject"
    path.write_text(json.dumps(events), encoding="utf-8")

    with pytest.raises(StateCorruptionError):
        journal.status()


def test_hash_cursor_pages_remain_stable_across_appends(tmp_path):
    path = tmp_path / "review_decision_journal.json"
    journal = ReviewDecisionJournal(path)
    journal.sync([
        review_row("proposal-a"),
        review_row("proposal-b"),
        review_row("proposal-c"),
    ])

    first = journal.page(limit=1)
    assert [event["sequence"] for event in first["items"]] == [3]
    assert first["next_cursor"] is not None

    journal.sync([
        review_row("proposal-a"),
        review_row("proposal-b"),
        review_row("proposal-c"),
        review_row("proposal-d"),
    ])
    second = journal.page(limit=1, cursor=first["next_cursor"])
    newest = journal.page(limit=2)
    empty = journal.page(limit=0)

    assert [event["sequence"] for event in second["items"]] == [2]
    assert [event["sequence"] for event in newest["items"]] == [4, 3]
    assert empty == {"items": [], "next_cursor": None, "count": 4}
    with pytest.raises(ValueError):
        journal.page(limit=1, cursor="unknown")


def test_valid_backup_is_reported_and_next_sync_repairs_primary(tmp_path):
    path = tmp_path / "review_decision_journal.json"
    journal = ReviewDecisionJournal(path)
    first = review_row("proposal-a")
    second = review_row("proposal-b")
    journal.sync([first])
    journal.sync([first, second])

    path.write_text("{broken", encoding="utf-8")
    recovered = ReviewDecisionJournal(path)
    status = recovered.status()

    assert status["valid"] is True
    assert status["source"] == "backup"
    assert status["recovered_from_backup"] is True
    assert status["count"] == 1

    repaired = recovered.sync([first, second])
    assert repaired["count"] == 2
    healthy = ReviewDecisionJournal(path).status()
    assert healthy["source"] == "primary"
    assert healthy["recovered_from_backup"] is False


def test_validation_checkpoint_is_invalidated_by_disk_change(tmp_path):
    path = tmp_path / "review_decision_journal.json"
    journal = ReviewDecisionJournal(path)
    journal.sync([review_row("proposal-a")])

    with patch.object(journal, "_validate", wraps=journal._validate) as validate:
        journal.status()
        journal.status()
        journal.page(limit=1)
        assert validate.call_count == 1

        events = json.loads(path.read_text(encoding="utf-8"))
        old_hash = events[0]["event_hash"]
        events[0]["event_hash"] = (
            ("0" if old_hash[0] != "0" else "1") + old_hash[1:]
        )
        path.write_text(json.dumps(events), encoding="utf-8")

        with pytest.raises(StateCorruptionError):
            journal.status()
        assert validate.call_count == 2
