import re
from pathlib import Path
from types import SimpleNamespace

from core.dialogue import LocalDialogueEngine


def test_dialogue_handler_delegates_once_to_the_canonical_pipeline():
    calls = []

    class Pipeline:
        def run(self, text):
            calls.append(text)
            return "پاسخ مسیر اصلی"

    pipeline = Pipeline()
    dialogue = SimpleNamespace(cognitive_pipeline=pipeline)

    assert LocalDialogueEngine.handle(dialogue, "ادامه بده") == "پاسخ مسیر اصلی"
    assert calls == ["ادامه بده"]
    assert dialogue._canonical_pipeline is pipeline


def test_dialogue_and_pipeline_have_one_execution_owner():
    dialogue_source = Path("core/dialogue.py").read_text(encoding="utf-8")
    pipeline_source = Path("core/cognitive_pipeline.py").read_text(encoding="utf-8")

    handle_bindings = re.findall(r"(?m)^LocalDialogueEngine\\.handle\\s*=", dialogue_source)
    run_methods = re.findall(r"(?m)^    def run\\(self, text\\):", pipeline_source)

    assert len(handle_bindings) == 1
    assert "LocalDialogueEngine.handle = _canonical_pipeline_handle" in dialogue_source
    assert len(run_methods) == 1
    assert not re.search(r"(?m)^CognitivePipeline\\.run\\s*=", pipeline_source)
    assert "_pipeline_v55_base" not in pipeline_source
