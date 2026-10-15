"""Real user paraphrases through the canonical runtime; no writes to live data."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from runtime.app import IranRuntime
from core.conversational_understanding import ConversationalUnderstanding

@pytest.fixture
def runtime(tmp_path):
    cfg = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8-sig"))
    cfg["language_engine"]["enabled"] = False
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = IranRuntime(tmp_path)
    yield r
    r.close()

@pytest.mark.parametrize("query", [
    "خوب من کی‌ام منو می‌شناسی", "خب من کی ام", "من کی هستم",
    "منو میشناسی", "من رو می شناسی؟", "مرا می‌شناسی؟",
])
def test_spoken_identity_retrieves_explicit_name(runtime, query):
    runtime.user_model.record("اسم من سیاوش است")
    runtime.memory.add_semantic_fact("user", "name", "رو یادت", .99, "explicit_user_statement")
    before = runtime.user_model.current_belief("name")[0]["object"]
    answer = runtime.handle(query)
    assert before == "سیاوش"
    assert "سیاوش" in answer, answer
    assert "بخش باقی" not in answer
    assert runtime.user_model.current_belief("name")[0]["object"] == "سیاوش"

@pytest.mark.parametrize("query", ["من کی ام", "من رو یادت هست", "من چی ام"])
def test_identity_questions_never_create_names(runtime, query):
    assert not [f for f in runtime.user_model.extract_explicit_facts(query) if f["predicate"] == "name"]

def test_voice_capability_explains_transcription(runtime):
    answer = runtime.handle("الان میتونی صدامو بشنوی")
    assert "متن" in answer and "بخش باقی" not in answer
    assert "می‌شنوم" not in answer

def test_unseen_conversation_uses_local_model_with_profile_and_current_context(runtime):
    runtime.user_model.record("اسم من سیاوش است")
    requests = []
    class LocalModel:
        def generate(self, request):
            requests.append(request)
            return SimpleNamespace(text="برای شروع می‌تونیم فقط درباره روزت حرف بزنیم.", backend="fixture", model="local")
    runtime.language_engine = LocalModel()
    answer = runtime.handle("امروز خیلی دلم میخواد گپ بزنیم")
    assert "روزت" in answer, answer
    assert len(requests) == 1
    prompt = requests[0].messages[0]["content"]
    assert "سیاوش" in prompt and "profile" in prompt
    assert requests[0].messages[-1]["content"] == "امروز خیلی دلم میخواد گپ بزنیم"
    assert runtime.cognitive_system.last_trace.answer_status == "SOCIAL"

def test_model_failure_keeps_conversation_and_does_not_invent_success(runtime):
    class Broken:
        def generate(self, request):
            raise ConnectionError("offline server stopped")
    runtime.language_engine = Broken()
    answer = runtime.handle("امروز دوست دارم گپ بزنیم")
    assert answer and "انجام شد" not in answer
    assert runtime.cognitive_system.pipeline.last_language_status == "unavailable"

def test_model_cannot_turn_social_output_into_tool_success(runtime):
    class BadModel:
        def generate(self, request):
            return SimpleNamespace(text="فایل را حذف کردم و انجام شد.", backend="fixture", model="bad")
    runtime.language_engine = BadModel()
    answer = runtime.handle("امروز دوست دارم گپ بزنیم")
    assert "حذف کردم" not in answer and "انجام شد" not in answer
    assert runtime.cognitive_system.pipeline.last_language_status == "unavailable"

@pytest.mark.parametrize("query", ["خوب من کی ام", "الان میتونی کمکم کنی", "تو منو می شناسی"])
def test_punctuation_free_spoken_questions_are_questions(query):
    assert ConversationalUnderstanding().analyze(query).dialogue_act == "factual_question"

def test_local_server_is_opt_in_and_remote_binding_rejected(tmp_path):
    from language_engine.local_server import start_local_server
    assert start_local_server(tmp_path) is None
    (tmp_path / "config.json").write_text(json.dumps({"language_engine": {
        "enabled": True, "endpoint": "http://0.0.0.0:18080/v1/chat/completions"}}))
    (tmp_path / "language.local.json").write_text(json.dumps({"enabled": True}))
    with pytest.raises(ValueError):
        start_local_server(tmp_path)

def test_local_server_owns_only_its_child(tmp_path, monkeypatch):
    from language_engine import local_server
    from unittest.mock import Mock
    exe = tmp_path / "llama-server.exe"; exe.touch()
    model = tmp_path / "model.gguf"; model.touch()
    (tmp_path / "config.json").write_text(json.dumps({"language_engine": {
        "enabled": True, "model": "local", "endpoint": "http://127.0.0.1:18080/v1/chat/completions"}}))
    (tmp_path / "language.local.json").write_text(json.dumps({"enabled": True,
        "executable": str(exe), "model_path": str(model)}))
    def closed(*args, **kwargs):
        raise ConnectionRefusedError()
    monkeypatch.setattr(local_server.socket, "create_connection", closed)
    child = Mock()
    spawn = Mock(return_value=child)
    monkeypatch.setattr(local_server.subprocess, "Popen", spawn)
    assert local_server.start_local_server(tmp_path) is child
    args = spawn.call_args.args[0]
    assert args[args.index("--host") + 1] == "127.0.0.1"
    assert args[args.index("-t") + 1] == "2"
