"""Regression: reference فارسی با stack خالی."""
from core.dialogue import ConversationState, ReferenceResolver

def test_empty_stack_falls_back():
    s = ConversationState()
    s.current_topic = "حافظه"
    res = ReferenceResolver().resolve("این بخش", s)
    assert res == "حافظه"
