import json, tempfile, unittest
from pathlib import Path
from runtime.app import IranRuntime
from core.voice import VoiceAssistant, WakeWord
from tools.desktop import DesktopTools

class FakeSTT:
    def transcribe_file(self,path): return "get system information"
class FakeTTS:
    def __init__(self): self.spoken=[]
    def speak(self,text): self.spoken.append(text); return {"spoken":True}

class JarvisIntegrationTests(unittest.TestCase):
    def make_runtime(self):
        root=Path(tempfile.mkdtemp()); cfg=json.loads(Path("config.json").read_text(encoding="utf-8-sig"))
        cfg["memory"]["db"]="data/test.db"; cfg["runtime"]["event_log"]="data/events.jsonl"; cfg["runtime"]["goals"]="data/goals.json"
        (root/"data").mkdir(); (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
        return IranRuntime(root)
    def test_real_filesystem_create_and_verify(self):
        with tempfile.TemporaryDirectory() as d:
            tools=DesktopTools(d); result=tools.create_folder("acceptance-folder")
            self.assertTrue(result["exists"]); self.assertTrue((Path(d)/"acceptance-folder").is_dir())
    def test_real_system_information(self):
        with tempfile.TemporaryDirectory() as d:
            info=DesktopTools(d).system_info()
            self.assertTrue(info["platform"]); self.assertTrue(info["python"])
    def test_sensitive_input_control_denied_by_default(self):
        r=self.make_runtime()
        try:
            out=r.computer_use.execute("type something","keyboard_type",{"text":"x"})
            self.assertFalse(out["success"]); self.assertEqual(out["verification"]["reason"],"permission_denied")
        finally:r.close()
    def test_failed_action_never_reports_success(self):
        r=self.make_runtime()
        try:
            out=r.computer_use.execute("missing","definitely_missing_tool")
            self.assertFalse(out["success"]); self.assertFalse(out["verification"]["verified"])
        finally:r.close()
    def test_voice_transport_uses_canonical_runtime_then_tts(self):
        r=self.make_runtime(); tts=FakeTTS()
        try:
            v=VoiceAssistant(r,FakeSTT(),tts)
            out=v.handle_audio_file("sample.wav")
            self.assertTrue(out["accepted"]); self.assertEqual(tts.spoken,[out["answer"]])
            self.assertEqual(r.cognitive_system.last_answer,out["answer"])
        finally:r.close()
    def test_wake_word_can_gate_voice(self):
        r=self.make_runtime()
        try:
            v=VoiceAssistant(r,FakeSTT(),wake_word=WakeWord("ایران",True))
            out=v.handle_audio_file("sample.wav")
            self.assertFalse(out["accepted"])
        finally:r.close()
    def test_registry_survives_restart(self):
        r=self.make_runtime(); names={x["name"] for x in r.registry.list()}; r.close()
        r2=IranRuntime(r.root)
        try:self.assertTrue({"screenshot","open_application","find_file","keyboard_type"} <= {x["name"] for x in r2.registry.list()})
        finally:r2.close()

if __name__=="__main__": unittest.main()
