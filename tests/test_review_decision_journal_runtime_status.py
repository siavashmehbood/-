"""Read-only runtime integration tests for the decision journal."""
import json
from types import SimpleNamespace

import pytest

from persistence import StateCorruptionError
from runtime.app import IranRuntime


def runtime_shell(tmp_path):
    runtime = IranRuntime.__new__(IranRuntime)
    runtime.root = tmp_path
    return runtime


def reviewed_row(proposal_id="proposal-a"):
    return {
        "proposal_id": proposal_id,
        "review_status": "reviewed",
        "chatgpt_decision": "learn",
        "reviewed_at": "2030-01-01T00:00:00+00:00",
        "provider": "fixture",
        "model": "openrouter/free",
    }


def test_runtime_status_and_page_are_read_only_for_empty_journal(tmp_path):
    runtime = runtime_shell(tmp_path)
    path = runtime._review_decision_journal_path()

    status = runtime.review_decision_journal_status()
    page = runtime.review_decision_journal_page(limit=10)

    assert status == {
        "valid": True,
        "count": 0,
        "head_hash": "0" * 64,
        "source": "empty",
        "recovered_from_backup": False,
    }
    assert page == {"items": [], "next_cursor": None, "count": 0}
    assert not path.exists()


def test_runtime_health_reports_corruption_without_authorizing_or_rewriting(tmp_path):
    runtime = runtime_shell(tmp_path)
    journal = runtime._review_decision_journal_store()
    journal.sync([reviewed_row()])

    path = runtime._review_decision_journal_path()
    backup = path.with_suffix(path.suffix + ".bak")
    if backup.exists():
        backup.unlink()
    events = json.loads(path.read_text(encoding="utf-8"))
    events[0]["decision"] = "reject"
    tampered = json.dumps(events)
    path.write_text(tampered, encoding="utf-8")

    with pytest.raises(StateCorruptionError):
        runtime.review_decision_journal_status()

    assert runtime.review_decision_journal_health() == {
        "valid": False,
        "count": None,
        "head_hash": None,
        "source": "corrupt",
        "recovered_from_backup": False,
        "error": "journal_integrity_error",
    }
    assert path.read_text(encoding="utf-8") == tampered


def test_learning_status_and_inspect_expose_observational_health(tmp_path):
    runtime = runtime_shell(tmp_path)
    runtime.learning_gate = SimpleNamespace(stats=lambda: {"pending": 0, "xp": 0})
    runtime.human_learning_pending = lambda limit=100000: []
    runtime.chatgpt_review_status = lambda: {"pending": 0}
    runtime.effect_learning = SimpleNamespace(
        stats=lambda: {"xp": 0, "validated": 0},
        state={"transfer_evaluations": []},
    )
    runtime.learning = SimpleNamespace(learned_lessons=[])
    runtime.cognitive_system = SimpleNamespace(
        inspect=lambda: {"runtime": "ok"}
    )

    learning = runtime.learning_status()
    inspection = runtime.inspect()

    assert learning["review_decision_journal"]["valid"] is True
    assert learning["review_decision_journal"]["source"] == "empty"
    assert inspection["runtime"] == "ok"
    assert inspection["review_decision_journal"] == learning["review_decision_journal"]
