"""Regression: نرمال‌سازی فارسی ZWNJ را حذف می‌کند."""
from core.dialogue import clean
from core.reference_intelligence import ReferenceIntelligence

def test_dialogue_clean_preserves_persian_zwnj():
    assert clean("حافظه\u200cاش") == "حافظه\u200cاش"
    assert clean("يادگيري") == "یادگیری"

def test_zwnj_removed_by_reference_clean():
    assert "\u200c" not in ReferenceIntelligence()._clean("حافظه\u200cاش")
