import json
from pathlib import Path

from core.learning_loop import OutcomeBackedLearning


class FakeLearning:
    def __init__(self):
        self.calls = []

    def record(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def test_unverified_outcome_never_teaches(tmp_path):
    engine = FakeLearning()
    loop = OutcomeBackedLearning(tmp_path / "outcomes.json", engine)

    result = loop.record_outcome(
        "بررسی فایل", "خواندن فایل", "نتیجه", "فایل موجود است",
        {"verified": False, "source": "self_score", "score": 1.0},
    )

    assert result["verified"] is False
    assert result["learned"] is False
    assert engine.calls == []


def test_verified_outcome_teaches_and_persists(tmp_path):
    engine = FakeLearning()
    path = tmp_path / "outcomes.json"
    loop = OutcomeBackedLearning(path, engine)

    result = loop.record_outcome(
        "بررسی فایل", "خواندن فایل", "فایل پیدا شد", "فایل موجود است",
        {"verified": True, "source": "filesystem_check", "score": 1.0},
        strategy="inspect-first",
        domain="project",
    )

    assert result["verified"] is True
    assert result["learned"] is True
    assert len(engine.calls) == 1
    assert path.exists()
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored[0]["verification_source"] == "filesystem_check"
    assert stored[0]["strategy"] == "inspect-first"


def test_recommendation_uses_only_verified_history(tmp_path):
    loop = OutcomeBackedLearning(tmp_path / "outcomes.json")
    loop.record_outcome(
        "ساخت گزارش", "روش الف", "خوب", "گزارش ساخته شد",
        {"verified": True, "source": "artifact_check", "score": .95},
        strategy="artifact-first",
        domain="report",
    )
    loop.record_outcome(
        "ساخت گزارش", "روش ب", "خوب", "گزارش ساخته شد",
        {"verified": False, "source": "answer_score", "score": .99},
        strategy="guess-first",
        domain="report",
    )

    recommendation = loop.recommend("ساخت گزارش", "report")
    assert recommendation["recommended_strategy"] == "artifact-first"
    assert recommendation["evidence_samples"] == 1


def test_verified_history_changes_future_action_choice(tmp_path):
    loop = OutcomeBackedLearning(tmp_path / "outcomes.json")
    loop.record_outcome(
        "recover a task", "slow_safe", "ok", "correct",
        {"verified": True, "source": "test-verifier", "score": 1.0},
        strategy="verified-recovery", domain="task",
    )
    choice = loop.recommend_action("recover a task again", ["fast_wrong", "slow_safe"], "task")
    assert choice["selected"] == "slow_safe"
    assert choice["ranked"][0]["verified_samples"] >= 1
