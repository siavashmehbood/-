import json
import shutil
from pathlib import Path

from core.dialogue import ConversationState
from runtime.app import IranRuntime


def test_project_goal_correction_survives_canonical_pipeline_and_restart(tmp_path):
    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("هدف دانا فروش کتاب است")
        assert runtime.dialogue.state.topic_goals["دانا"] == "فروش کتاب"
        assert "فروش کتاب" in runtime.handle("هدف دانا چی بود؟")

        runtime.handle("نه، هدفش فروش کتاب نبود، آموزش بود")
        assert runtime.dialogue.state.topic_goals["دانا"] == "آموزش"
        assert runtime.dialogue.state.goal_versions("دانا") == ["فروش کتاب", "آموزش"]
        assert "آموزش" in runtime.handle("هدف دانا چی بود؟")
        assert "فروش کتاب" in runtime.handle("نه، منظورم نسخه اول هدف بود")
        assert "آموزش" in runtime.handle("به نسخه جدید برگرد")
        assert runtime.dialogue.state.topic_goals["دانا"] == "آموزش"
    finally:
        runtime.close()

    restored = IranRuntime(tmp_path)
    try:
        assert restored.dialogue.state.topic_goals["دانا"] == "آموزش"
        assert restored.dialogue.state.goal_versions("دانا") == ["فروش کتاب", "آموزش"]
        assert "فروش کتاب" in restored.handle("نسخه اول هدف چی بود؟")
        assert "آموزش" in restored.handle("به نسخه جدید برگرد")
        assert "آموزش" in restored.handle("هدف دانا چی بود؟")
    finally:
        restored.close()


def test_specific_history_queries_survive_the_canonical_pipeline_and_restart(tmp_path):
    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime = IranRuntime(tmp_path)
    try:
        runtime.dialogue.state._push_topic("پروژه دانا")
        runtime.dialogue.state._push_topic("معماری شناختی")
        runtime.dialogue.state.save(runtime.dialogue.state_path)
        assert "پروژه دانا" in runtime.handle("موضوع اول چی بود؟")
        assert "معماری شناختی" in runtime.handle("موضوع دوم چی بود؟")

        runtime.handle("گفتم آفلاین باشه")
        runtime.handle("نه، منظورم بدون API بود")
        assert "بدون API" in runtime.handle("الان آخرین اصلاح چی بود؟")

        runtime.handle("من روی پروژه دانا کار می‌کنم")
        runtime.handle("پروژه ایران چیه؟")
        projects = runtime.handle("یادت هست من چه پروژه‌هایی گفتم؟")
        assert "دانا" in projects
        assert "ایران" in projects
    finally:
        runtime.close()

    restored = IranRuntime(tmp_path)
    try:
        assert "بدون API" in restored.handle("یک بار دیگه آخرین اصلاح رو بگو")
        projects = restored.handle("یادت هست من چه پروژه‌هایی گفتم؟")
        assert "دانا" in projects
        assert "ایران" in projects
    finally:
        restored.close()


def test_legacy_goal_state_migrates_to_version_history(tmp_path):
    state_path = tmp_path / "conversation_state.json"
    state_path.write_text(
        json.dumps({"topic_goals": {"دانا": "آموزش"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    state = ConversationState.load(state_path)

    assert state.topic_goals["دانا"] == "آموزش"
    assert state.goal_versions("دانا") == ["آموزش"]


def test_colloquial_ordinal_history_queries_use_canonical_topic_order(tmp_path):
    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime = IranRuntime(tmp_path)
    try:
        for topic in ("پایتون", "Django", "حافظه", "یادگیری", "معماری"):
            runtime.dialogue.state._push_topic(topic)
        runtime.dialogue.state.save(runtime.dialogue.state_path)

        assert "پایتون" in runtime.handle("اولین مورد چی بود؟")
        assert "یادگیری" in runtime.handle("چهارمیش چی بود؟")
        assert "معماری" in runtime.handle("پنجمیش چی بود؟")
        assert runtime.dialogue.state.current_topic == "معماری"
    finally:
        runtime.close()


def test_goal_correction_and_versions_bind_to_other_project(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("هدف دانا فروش کتاب است")
        runtime.handle("هدف اطلس آموزش است")
        assert "آموزش" in runtime.handle("هدف اطلس چی بود؟")
        runtime.handle("نه، هدفش آموزش نبود، پژوهش بود")
        assert runtime.dialogue.state.topic_goals["اطلس"] == "پژوهش"
        assert runtime.dialogue.state.topic_goals["دانا"] == "فروش کتاب"
        assert "آموزش" in runtime.handle("نسخه اول هدف چی بود؟")
        assert "پژوهش" in runtime.handle("به نسخه جدید برگرد")
    finally:
        runtime.close()
    restored = IranRuntime(tmp_path)
    try:
        assert "پژوهش" in restored.handle("هدف اطلس چی بود؟")
        assert "فروش کتاب" in restored.handle("هدف دانا چی بود؟")
    finally:
        restored.close()
