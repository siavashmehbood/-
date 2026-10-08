"""Public runtime acceptance without a PC, credentials or local model server."""
import json
import shutil
from pathlib import Path

from runtime.app import IranRuntime


def test_eight_turn_conversation_does_not_leak_unrelated_memory(tmp_path):
    source = Path(__file__).resolve().parents[1]
    config = json.loads((source / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/acceptance.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.memory.add("user", "اسم پروژه من دانا هست")
        runtime.memory.add("user", "من روی پایگاه داده PostgreSQL کار می‌کنم")
        turns = [
            "سلام",
            "من سیاوشم",
            "اسم من چیه؟",
            "کوتاه و طبیعی جواب بده",
            "امروز خسته‌ام",
            "هنوز خسته‌ام",
            "جواب تکراری نده",
            "پس الان چی کار کنم؟",
        ]
        answers = []
        for index, question in enumerate(turns):
            answer = runtime.handle(question)
            answers.append((question, answer))
            assert isinstance(answer, str) and answer.strip(), answers
            if index == 2:
                assert "سیاوش" in answer, answers
            if index >= 4:
                assert "دانا" not in answer and "PostgreSQL" not in answer, answers
        # Memory isolation must retain explicitly requested positive recall.
        recall = runtime.handle("اسم پروژه من چی بود؟")
        assert "دانا" in recall, (answers, recall)
    finally:
        runtime.close()
