from pathlib import Path

from core.cognitive_system import CognitiveSystem


def test_unified_system_has_single_canonical_contract():
    required = {
        "perception",
        "context",
        "memory",
        "knowledge",
        "reasoning",
        "planning",
        "generation",
        "verification",
        "commit",
        "learning",
        "autonomy",
        "improvement",
        "entrypoint",
    }
    contract = CognitiveSystem.architecture_contract(None)
    assert required.issubset(contract)
    assert contract["entrypoint"] == "CognitiveSystem.turn"


def test_runtime_routes_normal_turns_through_composition_root():
    source = Path("runtime/app.py").read_text(encoding="utf-8")
    assert "self.cognitive_system = _CognitiveSystem(self)" in source
    assert "return self.cognitive_system.dispatch(text)" in source
    assert "class CognitiveSystem" in Path("core/cognitive_system.py").read_text(encoding="utf-8")
