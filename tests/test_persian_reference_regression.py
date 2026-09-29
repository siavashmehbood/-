"""Regression: reference resolution برای چندنوبتی با stack فارسی."""
from core.dialogue import ConversationState, ReferenceResolver

def test_multi_turn_previous_topic_on_stack():
    s = ConversationState()
    s.topic_stack = ["اول", "دوم"]
    s.current_topic = "سوم"
    r = ReferenceResolver()
    # موضوع قبلی باید دوم باشد
    res = r.resolve("موضوع قبلی", s)
    # اگر ambiguous نباشد، باید مقدار صحیح بدهد یا حداقل stack قبلی را در candidates داشته باشد
    assert res == "دوم"
