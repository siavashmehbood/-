
"""Regression: reference فارسی با stack عمیق بعد از اصلاح."""
from core.dialogue import ConversationState, ReferenceResolver

def test_previous_topic_on_deep_stack():
    s = ConversationState()
    s.topic_stack = ["اول", "دوم", "سوم"]
    s.current_topic = "چهارم"
    assert ReferenceResolver().resolve("موضوع قبلی", s) == "سوم"
