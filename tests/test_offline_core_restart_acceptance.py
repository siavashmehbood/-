"""Canonical public runtime remains useful without a local language server."""
import json
from pathlib import Path
from runtime.app import IranRuntime


def test_offline_identity_and_project_memory_survive_restart(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["enabled"] = False
    config["memory"]["db"] = "data/offline.db"
    (tmp_path / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("اسم من سیاوش است")
        runtime.handle("اسم پروژه من دانا هست")
        runtime.handle("امروز خسته‌ام")
        runtime.handle("جواب تکراری نده")
        assert runtime.cognitive_system.architecture_contract()["decision_owner"] == "CognitiveSystem"
    finally:
        runtime.close()
    restored = IranRuntime(tmp_path)
    try:
        assert "سیاوش" in restored.handle("اسم من چیه؟")
        assert "دانا" in restored.handle("اسم پروژه من چی بود؟")
        unknown = restored.handle("شماره سریال لپ‌تاپ من چیه؟")
        assert any(marker in unknown for marker in ("UNKNOWN", "اطلاعات کافی", "نمی", "نامشخص")), unknown
    finally:
        restored.close()
