"""Regression یکپارچه هوش فارسی: reference + memory + normalization."""
from core.dialogue import ConversationState, clean
from core.reference_intelligence import ReferenceIntelligence
from memory.store import Memory
import tempfile, os

def test_integrated_persian_cognition():
    s = ConversationState(); s.topic_stack = ["A","B","C"]; s.current_topic = "D"
    assert ReferenceIntelligence().resolve("موضوع قبلی", s).candidate in ("C", "B", "")
    text = "حافظه\u200cاش"
    assert clean(text) == text
    with tempfile.TemporaryDirectory() as d:
        m = Memory(os.path.join(d,"t.db"))
        m.add("x", text)
        assert len(m.search("حافظه")) >= 1
        m.close()
