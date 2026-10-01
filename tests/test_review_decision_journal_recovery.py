import json
from unittest.mock import Mock

import pytest

from persistence import StateCorruptionError
from runtime.app import IranRuntime
from security.review_decision_journal import ReviewDecisionJournal


def review_row(proposal_id):
    return {
        "proposal_id": proposal_id,
        "review_status": "reviewed",
        "chatgpt_decision": "learn",
        "reviewed_at": "2030-01-01T00:00:00+00:00",
        "provider": "fixture",
        "model": "openrouter/free",
    }


def test_orphaned_atomic_temp_file_is_never_treated_as_committed(tmp_path):
    path = tmp_path / "review_decision_journal.json"
    first = review_row("committed")
    second = review_row("after-restart")
    journal = ReviewDecisionJournal(path)
    journal.sync([first])

    orphan = path.with_name(path.name + ".interrupted.tmp")
    orphan.write_text(
        json.dumps([{"proposal_id": "uncommitted"}]),
        encoding="utf-8",
    )

    restarted = ReviewDecisionJournal(path)
    assert restarted.status()["count"] == 1
    restarted.sync([first, second])
    page = restarted.page(limit=10)

    assert page["count"] == 2
    assert {event["proposal_id"] for event in page["items"]} == {
        "committed",
        "after-restart",
    }
    assert orphan.exists()


def test_truncated_primary_recovers_from_backup_and_repairs_on_sync(tmp_path):
    path = tmp_path / "review_decision_journal.json"
    first = review_row("first")
    second = review_row("second")
    journal = ReviewDecisionJournal(path)
    journal.sync([first])
    journal.sync([first, second])

    backup = path.with_suffix(path.suffix + ".bak")
    assert ReviewDecisionJournal(backup).status()["count"] == 1
    path.write_bytes(b'{"interrupted":')

    restarted = ReviewDecisionJournal(path)
    recovered = restarted.status()
    assert recovered["valid"] is True
    assert recovered["count"] == 1
    assert recovered["source"] == "backup"
    assert recovered["recovered_from_backup"] is True

    repaired = restarted.sync([first, second])
    persisted = json.loads(path.read_text(encoding="utf-8"))
    page = restarted.page(limit=10)

    assert repaired["count"] == 2
    assert len(persisted) == 2
    assert [event["sequence"] for event in persisted] == [1, 2]
    assert page["count"] == 2
    assert page["items"][0]["previous_hash"] == page["items"][1]["event_hash"]
    healthy = restarted.status()
    assert healthy["source"] == "primary"
    assert healthy["recovered_from_backup"] is False


def test_backup_recovery_is_visible_in_health_and_inspect(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    runtime = IranRuntime.__new__(IranRuntime)
    runtime.root = tmp_path
    runtime.cognitive_system = Mock()
    runtime.cognitive_system.inspect.return_value = {"version": "test"}

    first = review_row("first")
    second = review_row("second")
    journal = runtime._review_decision_journal_store()
    journal.sync([first])
    journal.sync([first, second])
    journal.path.write_bytes(b'{"interrupted":')

    health = runtime.review_decision_journal_health()
    inspected = runtime.inspect()["review_decision_journal"]

    assert health["valid"] is True
    assert health["source"] == "backup"
    assert health["recovered_from_backup"] is True
    assert inspected == health


@pytest.mark.parametrize(
    "corruption",
    ["tampered_primary", "tampered_backup", "unreadable_both"],
)
def test_corruption_matrix_fails_closed_without_rewriting_files(
    tmp_path, corruption
):
    path = tmp_path / "review_decision_journal.json"
    backup = path.with_suffix(path.suffix + ".bak")
    first = review_row("first")
    second = review_row("second")
    journal = ReviewDecisionJournal(path)
    journal.sync([first])
    journal.sync([first, second])

    if corruption == "tampered_primary":
        events = json.loads(path.read_text(encoding="utf-8"))
        events[0]["decision"] = "reject"
        path.write_text(json.dumps(events), encoding="utf-8")
    elif corruption == "tampered_backup":
        path.write_bytes(b'{"interrupted":')
        events = json.loads(backup.read_text(encoding="utf-8"))
        events[0]["decision"] = "reject"
        backup.write_text(json.dumps(events), encoding="utf-8")
    else:
        path.write_bytes(b'{"interrupted":')
        backup.write_bytes(b'["interrupted"')

    before = (path.read_bytes(), backup.read_bytes())
    with pytest.raises(StateCorruptionError):
        journal.status()
    assert (path.read_bytes(), backup.read_bytes()) == before

    with pytest.raises(StateCorruptionError):
        journal.sync([first, second])
    assert (path.read_bytes(), backup.read_bytes()) == before
