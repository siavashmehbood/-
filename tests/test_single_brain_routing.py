from pathlib import Path

from core.orchestrator import Orchestrator
from core.kernel import CognitiveKernel
from core.cognitive_core import AdvancedCognitiveCore


class _Canonical:
    def __init__(self):
        self.calls = []

    def dispatch(self, text):
        self.calls.append(("dispatch", text))
        return "canonical"

    def kernel_cycle_compat(self, text):
        self.calls.append(("kernel", text))
        return "kernel-canonical"

    def advanced_core_compat(self, text):
        self.calls.append(("advanced", text))
        return "advanced-canonical"


def test_legacy_decision_entrypoints_delegate_to_one_brain():
    canonical = _Canonical()

    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator._canonical_system = canonical
    assert orchestrator.handle("سلام") == "canonical"

    kernel = CognitiveKernel.__new__(CognitiveKernel)
    kernel._canonical_system = canonical
    assert kernel.cycle("بررسی") == "kernel-canonical"

    advanced = AdvancedCognitiveCore.__new__(AdvancedCognitiveCore)
    advanced._canonical_system = canonical
    assert advanced.begin("یاد بگیر") == "advanced-canonical"

    assert canonical.calls == [
        ("dispatch", "سلام"),
        ("kernel", "بررسی"),
        ("advanced", "یاد بگیر"),
    ]


def test_runtime_binds_legacy_components_to_cognitive_system():
    source = Path("runtime/app.py").read_text(encoding="utf-8")
    assert "self.cognitive_system.bind_legacy_adapters()" in source


def test_dialogue_pipeline_import_is_lazy():
    source = Path("core/dialogue.py").read_text(encoding="utf-8")
    assert "from core.cognitive_pipeline import CognitivePipeline" in source
    assert "def _canonical_pipeline_handle(self, text):\n    from core.cognitive_pipeline import CognitivePipeline" in source
