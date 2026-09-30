"""Regression: reasoning/planning فارسی با goal نرمال‌شده."""
from core.dialogue import clean
from core.reasoning_planning import ReasoningPlanTrace

def test_plan_goal_normalized():
    g = clean("برنامه‌ریزی برای حافظه\u200cاش")
    assert g == "برنامه\u200cریزی برای حافظه\u200cاش"
    trace = ReasoningPlanTrace(goal=g, intent="plan")
    assert trace.goal == g
