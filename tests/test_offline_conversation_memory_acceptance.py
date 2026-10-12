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
            if answer.startswith("UNKNOWN:"):
                trace = runtime.cognitive_system.last_trace
                raise AssertionError((
                    transcript,
                    getattr(trace, "answer_status", None),
                    getattr(trace, "verification_status", None),
                    getattr(trace, "verification_reasons", None),
                ))
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

def test_live_reproduction_restores_named_project_and_applies_scoped_goal_correction(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/live_project_context.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("هدف پروژه آلفا آموزش زبان انگلیسی است")
        runtime.handle("هدف پروژه دانا ساخت کتاب صوتی است")
        runtime.handle("چرا آسمان آبی است؟")
        returned = runtime.handle("برگردیم به پروژه آلفا؛ هدفش چی بود؟")
        assert "آموزش زبان انگلیسی" in returned, returned

        runtime.handle("هدف پروژه آلفا را اصلاح می‌کنم: آموزش برنامه‌نویسی پایتون است.")
        current_alpha = runtime.handle("هدف فعلی پروژه آلفا چیست؟")
        dana = runtime.handle("هدف پروژه دانا چیست؟")
        first_alpha = runtime.handle("نسخه اول هدف پروژه آلفا چی بود؟")
        assert "پایتون" in current_alpha, current_alpha
        assert "کتاب صوتی" in dana, dana
        assert "زبان انگلیسی" in first_alpha, first_alpha

        example = runtime.handle("برای هدف جدید آلفا یک مثال بزن.")
        continued = runtime.handle("ادامه بده.")
        assert "پایتون" in example and "برنامه" in example, example
        assert "پایتون" in continued or "برنامه" in continued, continued
    finally:
        runtime.close()


def test_emotional_followup_varies_after_persistent_short_style(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/live_emotional_context.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("کوتاه و طبیعی جواب بده")
        first = runtime.handle("امروز خسته‌ام")
        second = runtime.handle("هنوز خسته‌ام")
        runtime.handle("جواب تکراری نده")
        next_step = runtime.handle("پس الان چی کار کنم؟")
        assert first != second, (first, second)
        assert next_step not in {first, second}, (first, second, next_step)
        assert any(marker in next_step for marker in ("استراحت", "آب", "سبک‌تر", "کنار بذار")), next_step
        assert all(term not in (first + second + next_step).lower() for term in ("دانا", "postgresql"))
    finally:
        runtime.close()


def test_project_continuation_gives_a_concrete_next_learning_step(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/concrete_project_continuation.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("هدف پروژه آلفا یادگیری برنامه‌نویسی پایتون است")
        first = runtime.handle("برای شروع پایتون، متغیر یعنی چی؟")
        continued = runtime.handle("ادامه بده")
        assert first and continued, (first, continued)
        assert any(term in continued.lower() for term in ("پایتون", "python")), continued
        assert any(term in continued.lower() for term in ("متغیر", "ورودی", "عدد", "print", "تابع")), continued
        assert any(action in continued for action in ("بنویس", "بساز", "وارد کن", "اجرا کن", "تمرین کن")), continued
    finally:
        runtime.close()


def test_project_followup_simplifies_the_current_goal(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/project_simplification.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("هدف پروژه آلفا آموزش برنامه‌نویسی پایتون است")
        continuation = runtime.handle("ادامه بده")
        simpler = runtime.handle("همونو ساده‌تر بگو")
        assert continuation != simpler, (continuation, simpler)
        assert "آلفا" in simpler and "برنامه‌نویسی پایتون" in simpler, simpler
        assert any(action in simpler for action in ("انجام بده", "بنویس", "تمرین کن")), simpler
        assert "کدام واژه" not in simpler, simpler
    finally:
        runtime.close()


def test_project_name_recall_ignores_stored_question_after_restart(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/project_name_recall.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.memory.add("user", "اسم پروژه من دانا هست")
        first = runtime.handle("اسم پروژه من چی بود؟")
        assert "دانا" in first and "چی" not in first, first
    finally:
        runtime.close()

    restored = IranRuntime(tmp_path)
    try:
        recalled = restored.handle("اسم پروژه من چی بود؟")
        assert "دانا" in recalled and "چی" not in recalled, recalled
    finally:
        restored.close()


def test_identity_and_project_updates_answer_the_current_turn(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/current_turn_acknowledgements.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        intro = runtime.handle("من سیاوشم")
        assert "سیاوش" in intro and "UNKNOWN" not in intro, intro

        initial = runtime.handle("هدف پروژه آلفا آموزش زبان انگلیسی است")
        assert "آلفا" in initial and "آموزش زبان انگلیسی" in initial, initial
        correction = runtime.handle(
            "هدف پروژه آلفا را اصلاح می‌کنم: آموزش برنامه‌نویسی پایتون است."
        )
        assert "آلفا" in correction and "پایتون" in correction, correction
        current = runtime.handle("هدف فعلی پروژه آلفا چیست؟")
        assert "پایتون" in current, current

        topic_ack = runtime.handle("موضوع اصلی ما پروژه IRAN است.")
        assert "IRAN" in topic_ack and "دانا" not in topic_ack, topic_ack
        continuation = runtime.handle("همون قبلی رو ادامه بده")
        assert any(topic in continuation for topic in ("IRAN", "ایران", "پروژه")), continuation
        assert "ادامه می‌دهم" not in continuation, continuation
    finally:
        runtime.close()


def test_why_questions_keep_their_subject_and_short_why_uses_dialogue_context(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/why_context.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("هدف پروژه آلفا آموزش برنامه‌نویسی پایتون است")
        explicit = runtime.handle("چرا آسمان آبی است؟")
        assert "آلفا" not in explicit and "پایتون" not in explicit, explicit
        assert "ادامه را از" not in explicit and "مبنا می‌گیرم" not in explicit, explicit
        assert explicit.startswith("UNKNOWN:") or ("آسمان" in explicit and "پراکندگی" in explicit), explicit

        runtime.handle("موضوع اصلی ما پروژه ایران است.")
        contextual = runtime.handle("چرا؟")
        assert "پروژه ایران" in contextual or "کدام بخش" in contextual, contextual
    finally:
        runtime.close()


def test_name_recall_uses_the_current_explicit_name_naturally(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/natural_name_recall.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("من سیاوشم")
        answer = runtime.handle("اسم من چیه؟")
        assert "سیاوش" in answer and any(marker in answer for marker in ("اسم تو", "اسمت")), answer
        assert "اسم مورد" not in answer, answer
    finally:
        runtime.close()


def test_name_is_not_replaced_by_unrelated_first_person_verb_after_restart(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/name_stability.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("من سیاوشم")
        runtime.handle("من دارم امروز برنامه‌ریزی می‌کنم.")
        for sentence in (
            "من دارم.",
            "من می‌خواهم.",
            "من می‌کنم.",
            "من می‌روم.",
            "من می‌دانم.",
            "من نیستم.",
            "من نبودم.",
            "من رفتم.",
            "من کردم.",
            "من دیدم.",
            "من گفتم.",
            "من نمی‌دانم.",
        ):
            runtime.handle(sentence)
        current = runtime.handle("اسم من چیه؟")
        assert "سیاوش" in current, current
        assert "دار" not in current, current
    finally:
        runtime.close()

    restored = IranRuntime(tmp_path)
    try:
        current = restored.handle("اسم من چیه؟")
        assert "سیاوش" in current, current
        assert "دار" not in current, current
    finally:
        restored.close()


def test_unanswered_question_is_recalled_after_restart(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/unanswered_question.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    original_question = "عدد دقیق پرتاب آزمایشی ماهوارهٔ ناشناس من در سال ۱۹۸۷ چه بود؟"
    runtime = IranRuntime(tmp_path)
    try:
        answer = runtime.handle(original_question)
        assert answer.startswith("UNKNOWN:") or any(
            marker in answer for marker in ("اطلاعات کافی", "نمی‌خواهم حدس", "نامشخص")
        ), answer
        assert original_question in runtime.dialogue.state.unresolved_questions
        runtime.handle("نه، منظورم این نبود؛ دربارهٔ خودِ پرسش حرف می‌زنم.")
    finally:
        runtime.close()

    restored = IranRuntime(tmp_path)
    try:
        recalled = restored.handle("سؤال بی‌جواب قبلیم چی بود؟")
        assert original_question in recalled, recalled
        assert "نام پروژه" not in recalled
    finally:
        restored.close()


def test_current_question_about_unanswered_topics_is_not_history_recall(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/current_unanswered_topic.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        answer = runtime.handle("چرا بعضی سؤال‌ها بی‌جواب می‌مانند؟")
        assert "سؤال بی‌جواب قبلی‌ات این بود" not in answer, answer
        assert "سؤال بی‌جوابی در سابقهٔ گفتگو پیدا نکردم" not in answer, answer
    finally:
        runtime.close()


def test_followup_after_topic_change_does_not_resume_old_project(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/topic_shift_followup.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("هدف پروژه آلفا یادگیری برنامه‌نویسی پایتون است")
        first_topic = runtime.handle("حافظه در ایران چیه؟")
        continued = runtime.handle("ادامه بده")

        assert "حافظه" in first_topic, first_topic
        assert "حافظه" in continued and "اطلاعات" in continued, continued
        assert "پایتون" not in continued and "پروژهٔ «آلفا»" not in continued, continued
    finally:
        runtime.close()


def test_followup_after_persistent_style_keeps_the_previous_topic(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/style_followup_context.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        first = runtime.handle("حافظه در ایران چیه؟")
        runtime.handle("از این به بعد کوتاه و طبیعی جواب بده")
        continued = runtime.handle("ادامه بده")

        assert "حافظه" in first, first
        assert continued != first, (first, continued)
        assert "حافظه" in continued and "مورد مرتبط" in continued, continued
        assert "کوتاه" not in continued and "جواب بده" not in continued, continued
    finally:
        runtime.close()


def test_generic_python_followups_add_explanation_example_and_next_detail(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/python_followups.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        first = runtime.handle("پایتون چیه؟")
        continued = runtime.handle("ادامه بده")
        assert "پایتون" in first and "زبان" in first, first
        assert continued != first, (first, continued)
        assert "متغیر" in continued and "print" in continued, continued
        assert "روی یک مورد مشخص اجرا کن" not in continued, continued
    finally:
        runtime.close()

    explain_root = tmp_path / "explain"
    explain_root.mkdir()
    (explain_root / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    explain = IranRuntime(explain_root)
    try:
        first = explain.handle("پایتون چیه؟")
        expanded = explain.handle("همونو توضیح بده")
        assert "پایتون" in expanded and expanded != first, (first, expanded)
        assert "جزئیات سخت‌افزار" in expanded or "کارهای مختلف" in expanded, expanded
        assert "همان نکته را به کار ببری" not in expanded, expanded
    finally:
        explain.close()

    example_root = tmp_path / "example"
    example_root.mkdir()
    (example_root / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    example = IranRuntime(example_root)
    try:
        first = example.handle("پایتون چیه؟")
        demonstrated = example.handle("مثال بزن")
        assert "پایتون" in demonstrated and demonstrated != first, (first, demonstrated)
        assert "print" in demonstrated and "5" in demonstrated, demonstrated
        assert "در یک مورد کوچک" not in demonstrated, demonstrated
    finally:
        example.close()


def test_why_after_supported_python_definition_gives_a_grounded_reason(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/python_why_followup.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        first = runtime.handle("پایتون چیه؟")
        explanation = runtime.handle("چرا؟")
        assert "پایتون" in first and "زبان" in first, first
        assert "پایتون" in explanation and "جزئیات سخت‌افزار" in explanation, explanation
        assert "منظورت دلیل پاسخ" not in explanation, explanation
        assert not explanation.rstrip().endswith("؟"), explanation
    finally:
        runtime.close()


def test_no_repeat_style_does_not_cycle_during_a_long_emotional_followup(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/no_repeat_cycle.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        first = runtime.handle("امروز خسته‌ام")
        runtime.handle("جواب تکراری نده")
        assert "no_repeat" in runtime.dialogue.state.response_style, runtime.dialogue.state.response_style
        answers = [first]
        for _ in range(6):
            answers.append(runtime.handle("امروز خسته‌ام"))
        for index, current in enumerate(answers[1:], 1):
            if current in answers[:index]:
                recent = runtime.dialogue.state.references.get("recent_non_style_answers", [])
                summary = [(row.get("answer_type"), row.get("answer", "")[:90]) for row in recent[-4:] if isinstance(row, dict)]
                raise AssertionError(f"repeat at index {index}; style={runtime.dialogue.state.response_style}; recent={summary}; answers={answers}")
            relevant = ("خسته", "خستگی", "هم‌صحبتی", "پیشنهاد", "کمکت", "گوش می‌دهم", "حالت", "استراحت", "انرژی", "درگیرکننده", "مکث", "کار کوچک", "حرف", "سبک‌تر", "کارهای", "عقب", "ساده‌تر", "حوصله", "راهکار", "فشار", "شروع")
            assert any(term in current for term in relevant), f"non-relevant response at {index}: {current!r}"
    finally:
        runtime.close()
