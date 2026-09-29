"""Regression: multi-turn context carry-over با current_topic و follow_up."""
from core.dialogue import ConversationState

def test_multi_turn_carry():
    s = ConversationState()
    s.current_topic = "معماری شناختی ایران"
    s.topic_stack = ["حافظه فارسی"]
    assert s.current_topic == "معماری شناختی ایران"
