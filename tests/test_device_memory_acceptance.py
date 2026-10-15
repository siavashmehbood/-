"""Regressions reproduced during Windows acceptance with persistent history."""
import json
from pathlib import Path
import pytest
from runtime.app import IranRuntime

@pytest.fixture
def runtime(tmp_path):
    config=json.loads((Path(__file__).parents[1]/"config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"]=False
    (tmp_path/"config.json").write_text(json.dumps(config),encoding="utf-8")
    r=IranRuntime(tmp_path)
    r.handle("من سیاوشم")
    r.handle("من روی پروژه دانا کار می‌کنم")
    r.memory.add("user","اسم پروژه من دانا هست")
    yield r
    r.close()

def test_compound_name_and_project_recall_answers_both_parts(runtime):
    answer=runtime.handle("اسم من چیه و درباره پروژه دانا چی یادت هست؟")
    assert "سیاوش" in answer and "دانا" in answer, answer
    assert not answer.startswith("UNKNOWN"), answer

def test_no_repeat_preserves_supported_project_recall_and_restart(runtime):
    runtime.handle("جواب تکراری نده")
    for _ in range(3):
        answer=runtime.handle("اسم پروژه من چی بود؟")
        assert "دانا" in answer and not answer.startswith("UNKNOWN"), answer
    root=runtime.root
    runtime.close()
    restored=IranRuntime(root)
    try:
        answer=restored.handle("اسم پروژه من چی بود؟")
        assert "دانا" in answer and not answer.startswith("UNKNOWN"), answer
    finally:
        restored.close()

def test_architecture_definition_does_not_echo_old_user_topic(runtime):
    runtime.memory.add("user","موضوع اصلی ما معماری شناختی ایران است.")
    answer=runtime.handle("معماری شناختی ایران چیست؟")
    assert "در حافظه مرتبط" not in answer, answer
    assert "حافظه" in answer and "یادگیری" in answer, answer
    assert not answer.startswith("UNKNOWN"), answer
