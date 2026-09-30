"""Acceptance regression for the durable online-review / human-approval boundary."""
import shutil
from pathlib import Path

from runtime.app import IranRuntime


def test_reviewer_approval_alone_does_not_apply_learning_after_restart(tmp_path):
    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime = IranRuntime(tmp_path)
    proposal = runtime.learning_gate.request(
        "knowledge.add_fact",
        {
            "subject": "reviewer-only restart fixture",
            "predicate": "must_remain_unlearned",
            "object": "until a human approves",
            "source": "deterministic acceptance fixture",
        },
        "reviewer approval must not apply this fact",
    )
    proposal_id = proposal["proposal_id"]
    reviewed_ids = []

    try:
        # The worker requires the product's internet-learning switch to be on,
        # but its deterministic transport below makes no network request.
        runtime.internet_access.enable()
        runtime.sync_chatgpt_learning_reviews()
        runtime.chatgpt_review_worker.transport = lambda row: (
            reviewed_ids.append(row["proposal_id"])
            or {
                "learn": True,
                "reason": "deterministic reviewer acceptance",
                "confidence": 0.99,
                "provider": "test-fixture",
                "model": "test-fixture:free",
            }
        )

        result = runtime.process_one_online_learning_review()

        assert result["reason"] == "reviewed"
        assert reviewed_ids == [proposal_id]
        assert runtime.learning_gate.get(proposal_id)["status"] == "pending"
        assert runtime.human_learning_pending()[0]["proposal_id"] == proposal_id
        assert runtime.knowledge.query("reviewer-only restart fixture") == []
    finally:
        runtime.close()

    # Reconstruct every durable component from disk. A reviewer decision must
    # still be only a handoff to the human queue after a process restart.
    restored = IranRuntime(tmp_path)
    try:
        review = restored.chatgpt_learning_review_status(proposal_id)
        assert review["reviewed"] is True
        assert review["row"]["chatgpt_decision"] == "learn"
        assert review["row"]["status"] == "human_pending"
        assert restored.learning_gate.get(proposal_id)["status"] == "pending"
        assert [row["proposal_id"] for row in restored.human_learning_pending()] == [proposal_id]
        assert restored.knowledge.query("reviewer-only restart fixture") == []
        assert restored.memory.lesson_search("reviewer-only restart fixture", limit=5) == []
    finally:
        restored.close()



def test_reviewer_rejection_stays_rejected_after_restart(tmp_path):
    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime = IranRuntime(tmp_path)
    proposal = runtime.learning_gate.request(
        "knowledge.add_fact",
        {
            "subject": "reviewer-rejected restart fixture",
            "predicate": "must_never_be_learned",
            "object": "insufficient evidence",
            "source": "deterministic rejection fixture",
        },
        "a reviewer rejection must remain final across restart",
    )
    proposal_id = proposal["proposal_id"]

    try:
        runtime.internet_access.enable()
        runtime.sync_chatgpt_learning_reviews()
        runtime.chatgpt_review_worker.transport = lambda row: {
            "learn": False,
            "reason": "deterministic insufficient evidence",
            "confidence": 0.99,
            "provider": "test-fixture",
            "model": "test-fixture:free",
        }

        result = runtime.process_one_online_learning_review()

        assert result["reason"] == "reviewed"
        assert result["learn"] is False
        assert runtime.learning_gate.get(proposal_id)["status"] == "rejected"
        assert runtime.human_learning_pending() == []
        assert runtime.knowledge.query("reviewer-rejected restart fixture") == []
        assert runtime.memory.lesson_search("reviewer-rejected restart fixture", limit=5) == []
    finally:
        runtime.close()

    restored = IranRuntime(tmp_path)
    try:
        review = restored.chatgpt_learning_review_status(proposal_id)
        assert review["reviewed"] is True
        assert review["row"]["chatgpt_decision"] == "reject"
        assert review["row"]["status"] == "rejected"
        assert restored.learning_gate.get(proposal_id)["status"] == "rejected"
        assert restored.human_learning_pending() == []
        assert restored.knowledge.query("reviewer-rejected restart fixture") == []
        assert restored.memory.lesson_search("reviewer-rejected restart fixture", limit=5) == []
    finally:
        restored.close()
