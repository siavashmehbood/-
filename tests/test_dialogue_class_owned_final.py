"""Regression coverage for class-owned LocalDialogueEngine behavior."""
import inspect
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core.dialogue import LocalDialogueEngine
from runtime.app import IranRuntime

SRC=Path(__file__).resolve().parents[1]


def make_runtime():
    root=Path(tempfile.mkdtemp(prefix="iran_dialogue_class_owned_"))
    shutil.copy(SRC/"config.json",root/"config.json")
    shutil.copytree(SRC/"data",root/"data")
    shutil.copytree(SRC/"cognitive",root/"cognitive")
    (root/"logs").mkdir(exist_ok=True)
    for name in (
        "conversation_state.json","conversation_events.json","context_tracker.json",
        "dialogue-class-owned.db","soar_epmem.sqlite",
    ):
        (root/"data"/name).unlink(missing_ok=True)
    cfg=json.loads((root/"config.json").read_text(encoding="utf-8-sig"))
    cfg["memory"]["db"]="data/dialogue-class-owned.db"
    cfg["runtime"]["event_log"]="logs/events.jsonl"
    cfg["runtime"]["goals"]="data/goals.json"
    (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
    return IranRuntime(root)


def test_dialogue_ownership_is_declared_on_the_class_not_module_tail():
    source=(SRC/"core"/"dialogue.py").read_text(encoding="utf-8")
    assert "LocalDialogueEngine.__init__ =" not in source
    assert "LocalDialogueEngine._memory =" not in source
    assert "LocalDialogueEngine.handle =" not in source
    assert "_chain_init" not in source
    assert "_memory_chain_context" not in source

    init_src=inspect.getsource(LocalDialogueEngine.__init__)
    memory_src=inspect.getsource(LocalDialogueEngine._memory)
    handle_src=inspect.getsource(LocalDialogueEngine.handle)
    assert "ChainReasoner" in init_src
    assert "working_context" in memory_src
    assert "_canonical_system" in handle_src


def test_runtime_dialogue_initializes_chain_reasoner_and_delegates_to_one_brain():
    r=make_runtime()
    try:
        assert r.dialogue.chain_reasoner is not None
        assert r.dialogue.last_chain_result is None
        assert getattr(r.dialogue,"_canonical_system",None) is r.cognitive_system
        answer=r.dialogue.handle("سلام")
        assert str(answer).strip()
        assert r.cognitive_system.architecture_contract()["decision_owner"]=="CognitiveSystem"
    finally:
        r.close()


def test_detached_dialogue_handle_fails_closed():
    obj=object.__new__(LocalDialogueEngine)
    with pytest.raises(RuntimeError):
        obj.handle("سلام")


def test_dialogue_memory_filters_current_turn_self_echo():
    r=make_runtime()
    try:
        original=r.memory.working_context
        r.memory.working_context=lambda query,limit:[
            ("user",query,1.0),
            ("user","زمینه قبلی",0.9),
        ]
        rows=r.dialogue._memory("این سؤال")
        assert rows==[("user","زمینه قبلی",0.9)]
        r.memory.working_context=original
    finally:
        r.close()
