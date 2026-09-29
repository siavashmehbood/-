"""Regression: multi-turn reference فارسی."""
from core.dialogue import ConversationState
from core.reference_intelligence import ReferenceIntelligence

def test_previous_topic_deep_stack():
    s = ConversationState()
    s.topic_stack = ["حافظه فارسی", "یادگیری", "برنامه‌ریزی"]
    s.current_topic = "نتیجه‌گیری"
    res = ReferenceIntelligence().resolve("موضوع قبلی", s)
    assert res.candidate in ("یادگیری", "برنامه‌ریزی", "")
