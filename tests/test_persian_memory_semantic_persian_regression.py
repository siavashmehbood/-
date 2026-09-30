"""Regression: semantic search با فارسی و ZWNJ."""
import tempfile, os
from memory.store import Memory

def test_semantic_search_persian_zwnj():
    with tempfile.TemporaryDirectory() as d:
        m = Memory(os.path.join(d,"db"))
        m.add_semantic_fact("حافظه\u200cفارسی","نوع","episودic",.6,"test")
        res = m.semantic_search("حافظه فارسی")
        assert len(res) >= 1
        assert "\u200c" not in res[0]["subject"]
