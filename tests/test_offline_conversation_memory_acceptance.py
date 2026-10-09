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


def test_public_runtime_reexpresses_instead_of_echoing_or_promising(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        for prompt in ("ساده‌تر بگو", "ساده‌تر توضیح بده"):
            original = runtime.handle("پروژه ایران چیه؟")
            simpler = runtime.handle(prompt)
            assert original not in simpler, (prompt, original, simpler)
            assert "شناختی" not in simpler, simpler
            assert not simpler.startswith("UNKNOWN"), simpler
        for prompt in ("بیشتر توضیح بده", "کامل توضیح بده"):
            original = runtime.handle("پروژه ایران چیه؟")
            expanded = runtime.handle(prompt)
            assert expanded != original
            assert "توضیح می‌دم" not in expanded, expanded
            assert "همان موضوع را مبنا" not in expanded, expanded
            assert "حافظه" in expanded and "یادگیری" in expanded, expanded
            assert len(expanded) > len(original), (original, expanded)
    finally:
        runtime.close()
