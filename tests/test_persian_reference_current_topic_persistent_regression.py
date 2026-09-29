"""Regression: همون قبلی رو ادامه بده باید current_topic حفظ کند."""
from core.dialogue import ConversationState
from core.reference_intelligence import ReferenceIntelligence

def test_previous_reference_keeps_current_topic():
    state = ConversationState()
    state.current_topic = "معماری شناختی ایران"
    state.topic_stack = ["حافظه فارسی", "یادگیری"]
    state.active_goal = "ادامه بحث"
    res = ReferenceIntelligence().resolve("همون قبلی رو ادامه بده", state)
    assert res.candidate == "معماری شناختی ایران", f"FAIL: {res.candidate}"
