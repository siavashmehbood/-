import json

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

    repaired = restarted.sync([first, second])
    persisted = json.loads(path.read_text(encoding="utf-8"))
    page = restarted.page(limit=10)

    assert repaired["count"] == 2
    assert len(persisted) == 2
    assert [event["sequence"] for event in persisted] == [1, 2]
    assert page["count"] == 2
    assert page["items"][0]["previous_hash"] == page["items"][1]["event_hash"]
