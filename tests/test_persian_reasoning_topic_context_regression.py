"""Regression: reasoning/planning با topic_stack فارسی."""
from core.dialogue import ConversationState
from core.reasoning_planning import ReasoningPlanTrace

def test_reasoning_context_topic_stack():
    s = ConversationState()
    s.topic_stack = ["حافظه فارسی", "یادگیری"]
    s.current_topic = "برنامه‌ریزی"
    trace = ReasoningPlanTrace(goal="بهبود حافظه فارسی", intent="plan")
    assert trace.goal == "بهبود حافظه فارسی"
    assert s.topic_stack == ["حافظه فارسی", "یادگیری"]
