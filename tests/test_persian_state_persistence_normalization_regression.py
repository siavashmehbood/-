
"""Regression: persistence normalization فارسی."""
from core.dialogue import ConversationState
import tempfile, os

def test_persistence_normalizes_persian():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "s.json")
        s = ConversationState()
        s.corrections = ["اشتباه\u200cه"]
        s.unresolved_questions = ["چرا\u200c؟"]
        s.topic_stack = ["موضوع\u200cقبلی"]
        s.save(path)
        s2 = ConversationState.load(path)
        assert all("\u200c" not in x for x in s2.corrections)
