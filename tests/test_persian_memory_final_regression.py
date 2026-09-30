"""Regression نهایی حافظه فارسی."""
from memory.store import Memory
import tempfile, os

def test_memory_persian_normalized_search():
    with tempfile.TemporaryDirectory() as d:
        m = Memory(os.path.join(d,"db"))
        m.add("t", "حافظه\u200cاش")
        assert len(m.search("حافظه")) >= 1
