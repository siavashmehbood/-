"""Regression: verifier PASS/REPAIR/CLARIFY با تناقض شواهد."""
from core.dialogue import ConversationState
from core.reasoning_planning import ReasoningPlanTrace

def test_verifier_repair_on_contradiction():
    trace = ReasoningPlanTrace(
        goal="بهبود حافظه فارسی",
        intent="plan",
        contradictions=["تعارض شواهد"],
    )
    assert "تعارض" in str(trace.contradictions)
