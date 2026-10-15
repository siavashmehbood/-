import json,sys,threading,time,wave
from pathlib import Path
from types import SimpleNamespace
import pytest
from core.offline_voice import OfflineVoice,create_offline_voice
from core.voice import PiperTextToSpeech,VoskSpeechToText

def audio_file(path):
    with wave.open(str(path),"wb") as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000)
        audio.writeframes(bytes(320))

def test_synthesis_uses_utf8_and_does_not_claim_playback(tmp_path,monkeypatch):
    calls=[]
    def run(args,**kwargs):
        calls.append(kwargs)
        audio_file(args[args.index("--output_file")+1])
    monkeypatch.setattr("core.voice.subprocess.run",run)
    result=PiperTextToSpeech("piper","model").speak("سلام سیاوش")
    try:
        assert calls[0]["input"]=="سلام سیاوش"
        assert calls[0]["encoding"]=="utf-8"
        assert result["synthesized"] and result["spoken"] is False
    finally:Path(result["artifact"]).unlink()

def test_playback_cleanup_even_when_speaker_fails(tmp_path):
    path=tmp_path/"out.wav";audio_file(path)
    tts=SimpleNamespace(speak=lambda text:{"artifact":str(path)})
    def fail(path):raise OSError("speaker unavailable")
    voice=OfflineVoice(None,tts,playback=fail)
    with pytest.raises(OSError):voice.speak("سلام")
    assert not path.exists()

def test_cancelled_capture_never_returns_a_command():
    holder={}
    def listen(**kwargs):
        holder["voice"].cancel()
        return "یک دستور"
    voice=OfflineVoice(SimpleNamespace(listen=listen),None)
    holder["voice"]=voice
    assert voice.listen()=={"ok":False,"reason":"cancelled"}

def test_cancel_after_synthesis_does_not_play_and_removes_artifact(tmp_path):
    path=tmp_path/"out.wav";audio_file(path)
    played=[]
    voice=OfflineVoice(None,None,playback=lambda path:played.append(path))
    def synthesize(text):
        voice.cancel()
        return {"artifact":str(path)}
    voice.tts=SimpleNamespace(speak=synthesize)
    assert voice.speak("سلام")["reason"]=="cancelled"
    assert played==[] and not path.exists()

def test_model_is_loaded_once_for_multiple_recognizers(tmp_path,monkeypatch):
    loads=[]
    model=object()
    fake=SimpleNamespace(Model=lambda path:(loads.append(path) or model),
                         KaldiRecognizer=lambda m,rate:(m,rate))
    monkeypatch.setitem(sys.modules,"vosk",fake)
    stt=VoskSpeechToText(tmp_path)
    assert stt._recognizer()==stt._recognizer()==(model,16000)
    assert len(loads)==1

def test_unconfigured_voice_does_not_break_text_mode(tmp_path):
    voice,reason=create_offline_voice(tmp_path)
    assert voice is None and reason
    (tmp_path/"voice.local.json").write_text("[]",encoding="utf-8")
    voice,reason=create_offline_voice(tmp_path)
    assert voice is None and reason

def test_gui_voice_uses_canonical_runtime_and_remains_responsive(tmp_path,monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    import gui,core.offline_voice
    source=Path(__file__).parents[1]
    cfg=json.loads((source/"config.json").read_text(encoding="utf-8-sig"))
    cfg["language_engine"]["enabled"]=False
    (tmp_path/"config.json").write_text(json.dumps(cfg),encoding="utf-8")
    class FakeVoice:
        def __init__(self):self.cancelled=threading.Event();self.spoken=[]
        def prepare(self):self.cancelled.clear()
        def cancel(self):self.cancelled.set()
        def listen(self):time.sleep(.2);return {"ok":True,"text":"۲ + ۳ چند میشه؟"}
        def speak(self,text):self.spoken.append(text);time.sleep(.2);return {"ok":True,"played":True}
    voice=FakeVoice()
    monkeypatch.setattr(core.offline_voice,"create_offline_voice",lambda root:(voice,""))
    monkeypatch.setattr(gui,"ROOT",tmp_path)
    app=QApplication.instance() or QApplication([])
    window=gui.ChatWindow()
    assert "تنظیم شده" in window.assistant_state.text()
    window.autonomy_timer.stop();window.chatgpt_review_timer.stop()
    ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start(10)
    window.start_voice_input()
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.002)
        if voice.spoken and not window.busy and not window._jobs:break
    timer.stop()
    try:
        assert voice.spoken==["5"]
        assert window.last_answer=="5"
        assert len(ticks)>=10 and max(b-a for a,b in zip(ticks,ticks[1:]))<.25
        assert window.runtime.internet_access.status()["enabled"] is False
    finally:
        window.close();app.processEvents()

def test_gui_stop_discards_late_microphone_result(tmp_path,monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtWidgets import QApplication
    import gui,core.offline_voice
    cfg=json.loads((Path(__file__).parents[1]/"config.json").read_text(encoding="utf-8-sig"))
    cfg["language_engine"]["enabled"]=False
    (tmp_path/"config.json").write_text(json.dumps(cfg),encoding="utf-8")
    cancelled=threading.Event()
    def listen():
        time.sleep(.2)
        return {"ok":True,"text":"۲ + ۳ چند میشه؟"}
    voice=SimpleNamespace(prepare=cancelled.clear,cancel=cancelled.set,listen=listen)
    monkeypatch.setattr(core.offline_voice,"create_offline_voice",lambda root:(voice,""))
    monkeypatch.setattr(gui,"ROOT",tmp_path)
    app=QApplication.instance() or QApplication([])
    window=gui.ChatWindow();window.autonomy_timer.stop();window.chatgpt_review_timer.stop()
    window.start_voice_input();window.stop_operation()
    deadline=time.monotonic()+3
    while window._jobs and time.monotonic()<deadline:
        app.processEvents();time.sleep(.002)
    try:
        assert cancelled.is_set()
        assert not window.messages and not window.busy and not window._jobs
    finally:
        window.close();app.processEvents()
