"""Device-independent final acceptance; local sockets are real backend transport."""
import json
import runpy
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest
from core.voice import PiperTextToSpeech, VoskSpeechToText
from language_engine.backends.local_http import LocalHTTPBackend
from language_engine import GenerationRequest
from providers.reviewer import ReviewerProvider, ReviewFailure, decision
from runtime.app import IranRuntime

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), -1, 2])
def test_invalid_confidence_is_not_human_eligible(value):
    with pytest.raises(ReviewFailure):
        decision({"learn": True, "confidence": value})

@pytest.mark.parametrize("corrections", [[None], [123], [{}], [""], [float("nan")], ["x"] * 51])
def test_broken_corrections_are_rejected(corrections):
    with pytest.raises(ReviewFailure):
        decision({"learn": True, "corrections": corrections})

def test_model_failover_shares_one_time_budget(monkeypatch):
    provider = ReviewerProvider("openrouter", {"enabled": True, "dynamic_free_models": True})
    monkeypatch.setattr(provider, "availability", lambda: ("AVAILABLE", ""))
    elapsed = [0.0]
    monkeypatch.setattr("providers.reviewer.time.monotonic", lambda: elapsed[0])
    def models():
        elapsed[0] += 3
        return ["one:free", "two:free", "three:free"]
    monkeypatch.setattr(provider, "review_models", models)
    observed = []
    def fail(candidate, model):
        observed.append((model, provider.timeout))
        elapsed[0] += provider.timeout
        raise ReviewFailure("timeout")
    monkeypatch.setattr(provider, "_review_with_model", fail)
    with pytest.raises(ReviewFailure, match="review_budget_exhausted"):
        provider.review({})
    assert observed == [("one:free", 7.0)]
    assert provider.timeout == 10

def test_revocation_stops_next_model_even_after_reenable(monkeypatch, tmp_path):
    from security.internet_access import InternetAccessManager
    internet = InternetAccessManager(tmp_path / "internet.json")
    internet.enable()
    provider = ReviewerProvider("openrouter", {"enabled": True, "dynamic_free_models": True})
    provider._request_permission = (internet, internet.status()["generation"])
    monkeypatch.setattr(provider, "availability", lambda: ("AVAILABLE", ""))
    monkeypatch.setattr(provider, "review_models", lambda: ["one:free", "two:free"])
    calls = []
    def fail(candidate, model):
        calls.append(model)
        internet.disable()
        internet.enable()
        raise ReviewFailure("timeout")
    monkeypatch.setattr(provider, "_review_with_model", fail)
    with pytest.raises(ReviewFailure, match="internet_permission_changed"):
        provider.review({})
    assert calls == ["one:free"]

def write_wav(path, rate=16000):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\0\0" * 100)

def test_piper_synthesis_does_not_claim_playback(tmp_path, monkeypatch):
    def synthesize(args, **kwargs):
        write_wav(args[-1])
    monkeypatch.setattr("core.voice.subprocess.run", synthesize)
    result = PiperTextToSpeech(model_path="fixture.onnx").speak("سلام")
    try:
        assert result["synthesized"] is True
        assert result["spoken"] is False
        assert Path(result["artifact"]).is_file()
    finally:
        Path(result["artifact"]).unlink()

def test_invalid_wav_rate_fails_before_loading_optional_model(tmp_path, monkeypatch):
    wav = tmp_path / "wrong.wav"
    write_wav(wav, 44100)
    stt = VoskSpeechToText("missing")
    monkeypatch.setattr(stt, "_recognizer", lambda: pytest.fail("invalid WAV reached model"))
    with pytest.raises(ValueError, match="sample rate"):
        stt.transcribe_file(wav)

@pytest.mark.parametrize("content,expected", [
    ("سلام، هستم. بگو چه کمکی می‌خوای.", "سلام، هستم. بگو چه کمکی می‌خوای."),
    (None, "سلام، آره هستم. بگو از کجا شروع کنیم."),
    ({"tool": "delete"}, "سلام، آره هستم. بگو از کجا شروع کنیم."),
    ("اسم تو علی است و یادگیری تایید شد", "سلام، آره هستم. بگو از کجا شروع کنیم."),
])
def test_public_runtime_calls_real_local_backend_and_keeps_authority(tmp_path, content, expected):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    config["language_engine"]["endpoint"] = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    runtime = IranRuntime(tmp_path)
    try:
        assert runtime.handle("سلام هستی؟") == expected
        assert len(requests) == 1
        assert requests[0]["model"] == config["language_engine"]["model"]
        assert runtime.cognitive_system.last_answer == expected
        assert runtime.handle("۲ + ۳") and len(requests) == 1
        assert not runtime.knowledge.best_fact("اسم", "تو")
    finally:
        runtime.close()
        server.shutdown()
        server.server_close()
        thread.join()

def test_local_backend_refuses_redirect_before_remote_request():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(302)
            self.send_header("Location", "https://example.invalid/private")
            self.end_headers()
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        backend = LocalHTTPBackend("fixture", f"http://127.0.0.1:{server.server_port}/")
        with pytest.raises(ValueError, match="redirect"):
            backend.generate(GenerationRequest(messages=[]))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

def test_startup_failure_is_visible_and_logged():
    namespace = runpy.run_path(str(ROOT / "launch_gui.pyw"))
    with patch("runpy.run_path", side_effect=ImportError("PySide6 missing")), patch("os.chdir"), patch.object(Path, "open") as opened:
        assert namespace["main"]() == 1
        assert opened.call_args.kwargs["encoding"] == "utf-8"

def test_global_attempt_limit_counts_models_across_providers(tmp_path, monkeypatch):
    from providers.reviewer import ProviderManager
    from security.internet_access import InternetAccessManager
    internet = InternetAccessManager(tmp_path / "internet.json")
    internet.enable()
    calls = []
    providers = []
    for name in ("first", "second"):
        provider = ReviewerProvider("openrouter", {"enabled": True, "dynamic_free_models": True, "model_attempts": 3})
        provider.name = name
        monkeypatch.setattr(provider, "availability", lambda: ("AVAILABLE", ""))
        monkeypatch.setattr(provider, "review_models", lambda: ["a:free", "b:free", "c:free"])
        def fail(candidate, model):
            calls.append(model)
            raise ReviewFailure("timeout")
        monkeypatch.setattr(provider, "_review_with_model", fail)
        providers.append(provider)
    manager = ProviderManager(tmp_path, {"reviewers": {"max_attempts": 4}}, internet, providers)
    assert not manager.review({})["ok"]
    assert len(calls) == 4

@pytest.mark.skipif(__import__("os").name != "nt", reason="PowerShell launcher runs on Windows CI")
def test_windows_launcher_uses_project_venv_and_preserves_existing_process(tmp_path):
    import shutil
    import subprocess
    import sys
    root = tmp_path / "IRAN acceptance with spaces"
    root.mkdir()
    shutil.copy(ROOT / "launch_iran.ps1", root / "launch_iran.ps1")
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(root / ".venv")], check=True)
    (root / "launch_gui.pyw").write_text(
        "import json, os, sys\nfrom pathlib import Path\n"
        "Path('startup-result.json').write_text(json.dumps({'cwd':os.getcwd(),'exe':sys.executable}))\n",
        encoding="utf-8")
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", str(root / "gui.py")])
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                 "-File", str(root / "launch_iran.ps1")], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert sleeper.poll() is None
        record = json.loads((root / "startup-result.json").read_text())
        assert Path(record["cwd"]) == root
        assert Path(record["exe"]) == root / ".venv" / "Scripts" / "python.exe"
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=10)
