import shutil
from pathlib import Path

from core.dialogue import AnswerPlanner, CognitiveContext
from runtime.app import IranRuntime


def make_runtime(tmp_path):
    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path / "config.json")
    runtime = IranRuntime(tmp_path)
    runtime.internet_access.enable()
    return runtime


def guidance_for(runtime, query):
    return runtime.learning.adapt(query, "general", "general")["approved_lessons"]


def test_governed_learning_changes_unseen_planning_and_survives_restart(tmp_path):
    training_goal = "امن‌سازی ورودی کاربر"
    unseen_query = "برای ورودی کاربر ناشناخته چه بررسی‌ای انجام شود؟"
    lesson = "برای ورودی کاربر ناشناخته ابتدا اعتبارسنجی انجام بده و سپس نتیجه را مستقل بررسی کن."

    runtime = make_runtime(tmp_path)
    try:
        assert guidance_for(runtime, unseen_query) == []

        rejected = runtime.queue_learning_candidate(
            "memory.add_lesson",
            {"goal": training_goal, "lesson": "این درس نباید اعمال شود", "confidence": .95,
             "source": "growth-e2e-rejected", "domain": "general"},
            "rejected growth fixture",
        )
        runtime.chatgpt_review_worker.transport = lambda row: {
            "learn": False, "reason": "unsupported", "confidence": .95,
            "corrections": [], "provider": "fixture", "model": "free:fixture",
        }
        review = runtime.process_one_chatgpt_learning_review()
        assert review["proposal_id"] == rejected["proposal_id"] and review["learn"] is False
        assert runtime.human_learning_pending(10) == []
        assert guidance_for(runtime, unseen_query) == []
    finally:
        runtime.close()

    # Reviewer cooldown is durable and intentional. Start a new governed session
    # instead of bypassing or weakening the production rate limit.
    cooldown_path = tmp_path / "data" / "chatgpt_review_state.json"
    if cooldown_path.exists():
        cooldown_path.unlink()
    runtime = make_runtime(tmp_path)
    try:
        assert guidance_for(runtime, unseen_query) == []

        candidate = runtime.queue_learning_candidate(
            "memory.add_lesson",
            {"goal": training_goal, "lesson": lesson, "confidence": .95,
             "source": "growth-e2e", "domain": "general"},
            "governed growth fixture",
        )
        runtime.chatgpt_review_worker.transport = lambda row: {
            "learn": True, "reason": "supported", "confidence": .95,
            "corrections": [], "provider": "fixture", "model": "free:fixture",
        }
        review = runtime.process_one_chatgpt_learning_review()
        assert review["proposal_id"] == candidate["proposal_id"] and review["learn"] is True
        assert runtime.learning_gate.stats()["total"] == 0
        assert [x["proposal_id"] for x in runtime.human_learning_pending(10)] == [candidate["proposal_id"]]

        approved = runtime.approve_learning(candidate["proposal_id"], human_confirmed=True, source="growth_e2e_human")
        assert approved["ok"], approved
        learned = guidance_for(runtime, unseen_query)
        assert learned and learned[0]["lesson"] == lesson

        ctx = CognitiveContext(
            user_message=unseen_query, question_type="general", question_units=[unseen_query],
            learning_guidance={"approved_lessons": learned},
        )
        assert "apply_approved_lesson" in AnswerPlanner().plan(ctx).steps
    finally:
        runtime.close()

    restarted = make_runtime(tmp_path)
    try:
        learned = guidance_for(restarted, unseen_query)
        assert learned and learned[0]["lesson"] == lesson
        review = restarted.chatgpt_learning_review_status(candidate["proposal_id"])["row"]
        assert review["human_decision"] == "approved"
        assert review["human_source"] == "growth_e2e_human"
    finally:
        restarted.close()
