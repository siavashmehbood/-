from learning.learning_engine import LearningEngine
from core.dialogue import AnswerPlanner, CognitiveContext


def test_approved_lesson_is_real_content_and_reusable(tmp_path):
    e = LearningEngine(tmp_path / "experiences.json")
    row = e.record_approved_lesson({
        "goal": "پایتون حلقه for",
        "lesson": "حلقه for برای پیمایش مجموعه استفاده می‌شود و باید با یک مثال مستقل آزموده شود.",
        "result": "تست مستقل موفق شد",
        "score": .95,
        "domain": "programming",
        "intent": "learning",
        "strategy": "evidence-first",
        "evidence": "execution:test-1",
    }, "proposal-1")
    assert row["lesson"].startswith("حلقه for")
    assert row["status"] == "approved"
    guidance = e.adapt("پایتون حلقه for", "learning", "programming")
    assert guidance["approved_lessons"]
    assert guidance["approved_lessons"][0]["lesson"].startswith("حلقه for")


def test_planner_changes_plan_when_approved_lesson_exists():
    ctx = CognitiveContext(
        user_message="پایتون حلقه for",
        question_type="general",
        question_units=["پایتون حلقه for"],
        learning_guidance={"approved_lessons": [{"lesson": "از شواهد و تست مستقل استفاده کن."}]},
    )
    plan = AnswerPlanner().plan(ctx)
    assert "apply_approved_lesson" in plan.steps
