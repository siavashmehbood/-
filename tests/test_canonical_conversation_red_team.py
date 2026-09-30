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
