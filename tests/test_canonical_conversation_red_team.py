import shutil
from pathlib import Path

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
        assert "آموزش" in runtime.handle("هدف دانا چی بود؟")
    finally:
        runtime.close()

    restored = IranRuntime(tmp_path)
    try:
        assert restored.dialogue.state.topic_goals["دانا"] == "آموزش"
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
