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


def test_short_style_changes_later_answers_and_survives_restart(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        baseline = runtime.handle("امروز ناراحتم")
        runtime.handle("از این به بعد کوتاه و طبیعی جواب بده")
        short = runtime.handle("امروز ناراحتم")
        assert len(short) < len(baseline), (baseline, short)
        assert "دانا" not in short
    finally:
        runtime.close()
    restored = IranRuntime(tmp_path)
    try:
        answer = restored.handle("امروز ناراحتم")
        assert len(answer) < len(baseline), (baseline, answer)
    finally:
        restored.close()


def test_followup_requests_deliver_memory_content_not_promises(tmp_path):
    config = json.loads((Path(__file__).parents[1]/"config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    (tmp_path/"config.json").write_text(json.dumps(config), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.memory.add("user", "اسم پروژه من دانا هست")
        runtime.handle("حافظه در ایران چیه؟")
        transcript = []
        for prompt in ("ادامه بده", "همونو توضیح بده", "یه مثال بزن"):
            answer = runtime.handle(prompt); transcript.append((prompt, answer))
            assert not any(x in answer for x in ("ادامه می‌دهم", "مبنا می‌گیرم", "نمونه کوچک و مشخص")), transcript
            assert "دانا" not in answer, transcript
            if "مثال" in prompt:
                assert any(x in answer for x in ("فرض کن", "اگر بگویی", "مثلاً بگویی")), transcript
                assert any(x in answer for x in ("اسم", "نام", "سؤال", "پرس")), transcript
            else:
                assert any(x in answer for x in ("اطلاعات", "پیام", "ذخیره")), transcript
                assert any(x in answer for x in ("مرتبط", "بازیابی", "نگه")), transcript
    finally:
        runtime.close()


def test_explicit_project_correction_selects_named_project_and_keeps_history(tmp_path):
    config = json.loads((Path(__file__).parents[1]/"config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    (tmp_path/"config.json").write_text(json.dumps(config), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("هدف اطلس آموزش است")
        runtime.handle("هدف دانا فروش کتاب است")
        runtime.handle("نه، هدف اطلس آموزش نبود، پژوهش بود")
        assert "پژوهش" in runtime.handle("هدف اطلس چی بود؟")
        assert "فروش کتاب" in runtime.handle("هدف دانا چی بود؟")
        assert "آموزش" in runtime.handle("نسخه اول هدف اطلس چی بود؟")
    finally:
        runtime.close()
    restored = IranRuntime(tmp_path)
    try:
        assert "پژوهش" in restored.handle("هدف اطلس چی بود؟")
        assert "فروش کتاب" in restored.handle("هدف دانا چی بود؟")
    finally:
        restored.close()


def test_name_correction_history_and_unfinished_question_survive_restart(tmp_path):
    config = json.loads((Path(__file__).parents[1]/"config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    (tmp_path/"config.json").write_text(json.dumps(config), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("اسم من سامان است")
        runtime.handle("نه، اسم من سیاوش است")
        assert "سیاوش" in runtime.handle("اسم من چیه؟")
        runtime.handle("من خسته‌ام")
        assert "سیاوش" in runtime.handle("اسم من چیه؟")
        assert "سامان" in runtime.handle("قبلاً اسم من چی ثبت شده بود؟")
        question = "مقدار دقیق فروش ماه آینده اطلس چقدر است؟"
        answer = runtime.handle(question)
        assert answer.startswith("UNKNOWN"), answer
        assert question in runtime.dialogue.state.unresolved_questions
    finally:
        runtime.close()
    restored = IranRuntime(tmp_path)
    try:
        assert "سیاوش" in restored.handle("اسم من چیه؟")
        assert "سامان" in restored.handle("قبلاً اسم من چی ثبت شده بود؟")
        assert question in restored.dialogue.state.unresolved_questions
    finally:
        restored.close()
