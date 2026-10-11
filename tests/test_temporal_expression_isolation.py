from datetime import datetime, timedelta
import pytest
from core.language_engine import PersianLanguageEngine


@pytest.mark.parametrize("text, expression, offset", [
    ("فردا انجام بده", "فردا", 1),
    ("پس‌فردا انجام بده", "پس‌فردا", 2),
    ("پس فردا انجام بده", "پس‌فردا", 2),
    ("دیروز انجام شد", "دیروز", -1),
    ("امروز انجام بده", "امروز", 0),
])
def test_relative_day_resolves_once(text, expression, offset):
    now = datetime(2026, 10, 9, 3, 0)
    result = PersianLanguageEngine().temporal_context(text, now)
    assert result["raw"] == [expression]
    assert result["resolved"] == [{
        "expression": expression,
        "iso": (now + timedelta(days=offset)).isoformat(timespec="minutes"),
    }]


def test_multiple_days_are_retained_but_not_duplicate_substrings():
    result = PersianLanguageEngine().temporal_context(
        "امروز و پس‌فردا؛ پس‌فردا دوباره", datetime(2026, 10, 9)
    )
    assert result["raw"] == ["امروز", "پس‌فردا"]
    assert [row["expression"] for row in result["resolved"]] == ["امروز", "پس‌فردا"]


def test_long_expression_and_word_boundaries():
    engine = PersianLanguageEngine()
    assert engine.temporal_context("همین الان")["raw"] == ["همین الان"]
    assert engine.temporal_context("شبکه و صبحانه")["raw"] == []
