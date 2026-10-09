import json
import re
from pathlib import Path
import pytest
from runtime.app import IranRuntime


@pytest.mark.parametrize("question, expected", [
    ("۲ + ۳", 5), ("٢ + ٣", 5), ("2 + 3", 5),
    ("هفت به علاوه پنج", 12), ("ده منهای چهار", 6),
    ("سه ضربدر چهار", 12), ("هشت تقسیم بر دو", 4),
    ("۰ + ۷", 7), ("-۳ + ۵", 2),
])
def test_public_runtime_computes_offline_without_retrieval(tmp_path, question, expected):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.memory.add("assistant", "نتیجه محاسبه قبلی ۹۹۹ است")
        runtime.internet_access.disable()
        answer = runtime.handle(question)
        normalized = answer.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        assert re.search(r"(?<![\d.])" + str(expected) + r"(?![\d.])", normalized), answer
        assert "999" not in normalized, answer
        assert not answer.startswith("UNKNOWN"), answer
        trace = runtime.cognitive_system.last_trace
        assert trace is not None and trace.user_text == question, trace
    finally:
        runtime.close()


def test_public_runtime_division_by_zero_is_not_a_fact(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        answer = runtime.handle("۶ تقسیم بر صفر")
        assert "صفر" in answer and any(term in answer for term in ("تعریف", "مجاز", "نمی")), answer
    finally:
        runtime.close()
