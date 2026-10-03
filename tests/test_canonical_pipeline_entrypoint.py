"""Architecture regression for the canonical CognitivePipeline entrypoint."""
import inspect
from pathlib import Path

from core.cognitive_pipeline import CognitivePipeline


def test_cognitive_pipeline_has_one_canonical_run_owner():
    source=Path("core/cognitive_pipeline.py").read_text(encoding="utf-8")
    assert source.count("    def run(self, text):") == 1
    assert CognitivePipeline.run.__qualname__ == "CognitivePipeline.run"
    assert inspect.isfunction(CognitivePipeline.run)

    forbidden=(
        "_pipeline_run_legacy",
        "_pipeline_run_v41c",
        "_pipeline_v55_base",
        "_pipeline_v56_base",
        "_pipeline_v57_base",
        "_pipeline_v58_base",
        "_pipeline_v59_base",
        "_pipeline_v60_base",
        "_pipeline_v61_base",
        "_pipeline_v62_base",
        "_pipeline_v63_base",
        "_pipeline_self_correction_base",
        "_pipeline_v65_base",
        "_pipeline_v66_base",
    )
    assert not any(name in source for name in forbidden)


def test_canonical_pipeline_is_not_monkeypatched_at_module_scope():
    source=Path("core/cognitive_pipeline.py").read_text(encoding="utf-8")
    assert "CognitivePipeline.run =" not in source
    assert "setattr(CognitivePipeline" not in source
