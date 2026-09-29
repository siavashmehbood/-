"""Regression: reasoning/planning با topic_stack فارسی."""
from core.dialogue import ConversationState
from core.reasoning_planning import ReasoningPlanTrace

def test_reasoning_with_topic_stack():
    s = ConversationState()
    s.topic_stack = ["حافظه", "یادگیری"]
    s.current_topic = "برنامه‌ریزی"
    trace = ReasoningPlanTrace(goal="بهبود حافظه فارسی", intent="plan")
    assert trace.goal == "بهبود حافظه فارسی"

[executed on device: DESKTOP-QPTUEG0 (3d8d9e3e-a2ea-4bcd-9681-8684e4ca6979)]
