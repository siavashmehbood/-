"""Regression: حافظه فارسی ZWNJ را در _norm حذف می‌کند."""
from memory.store import Memory
import tempfile, os

def test_memory_norm_strips_zwnj():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem = Memory(db)
        mem.add("test", "حافظه\u200cاش")
        res = mem.search("حافظه")
        assert len(res) >= 1, "ZWNJ broke memory retrieval"
