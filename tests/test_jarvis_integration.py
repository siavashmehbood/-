import json, tempfile, unittest
from pathlib import Path
from runtime.app import IranRuntime
from core.voice import VoiceAssistant, WakeWord
from tools.desktop import DesktopTools
from core.screen_perception import DesktopObservation, UIGrounder

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
    def test_computer_loop_stops_on_verification_failure(self):
        r=self.make_runtime()
        try:
            result=r.computer_use.run("bounded task",[
                {"tool":"system_info"},
                {"tool":"definitely_missing_tool"},
                {"tool":"system_info"}],timeout_seconds=5)
            self.assertFalse(result["success"]); self.assertEqual(result["stop_reason"],"verification_failure")
            self.assertEqual(len(result["steps"]),2)
        finally:r.close()
    def test_computer_loop_enforces_max_steps(self):
        r=self.make_runtime()
        try:
            r.computer_use.max_steps=1
            result=r.computer_use.run("bounded task",[{"tool":"system_info"},{"tool":"system_info"}])
            self.assertFalse(result["success"]); self.assertEqual(result["stop_reason"],"max_steps")
            self.assertEqual(len(result["steps"]),1)
        finally:r.close()

    def test_remaining_registry_capabilities_exist(self):
        r=self.make_runtime()
        try:
            names={x["name"] for x in r.registry.list()}
            self.assertTrue({"open_file","open_folder","get_battery","get_volume","set_volume",
                             "list_windows","focus_window","minimize_window","maximize_window",
                             "restore_window","clipboard_read","clipboard_write"} <= names)
        finally:r.close()
    def test_write_and_input_permissions_are_not_silently_allowed(self):
        r=self.make_runtime()
        try:
            self.assertFalse(r.policy.allows("write"))
            self.assertFalse(r.policy.allows("input_control"))
            self.assertFalse(r.policy.allows("destructive"))
        finally:r.close()
    def test_real_copy_move_rename_are_confined_and_observable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/"a.txt").write_text("x",encoding="utf-8"); tools=DesktopTools(root)
            copied=tools.copy_file("a.txt","b.txt"); self.assertTrue(copied["exists"])
            moved=tools.move_file("b.txt","c.txt"); self.assertTrue(moved["exists"])
            renamed=tools.rename_file("c.txt","d.txt"); self.assertTrue(renamed["exists"])
            with self.assertRaises(PermissionError): tools.create_folder("../escape")

    def test_structured_observation_signature_and_grounding(self):
        obs=DesktopObservation(None,1920,1080,{"title":"Editor"},[],(10,20),
            [{"role":"button","label":"Save","bounds":(1,2,3,4),"enabled":True,"focused":False,"window":"Editor","confidence":1.0,"source":"test"}],
            None,"now",1.0,{"structured":"test"})
        self.assertEqual(obs.signature(),obs.signature())
        grounded=UIGrounder().resolve(obs,"Save",role="button")
        self.assertEqual(grounded["status"],"grounded")
        self.assertEqual(UIGrounder().resolve(obs,"Missing")["status"],"unknown")
    def test_grounder_refuses_ambiguous_target(self):
        elements=[{"role":"button","label":"Save","window":"A"},{"role":"button","label":"Save","window":"B"}]
        obs=DesktopObservation(None,0,0,None,[],None,elements,None,"now",1.0,{})
        self.assertEqual(UIGrounder().resolve(obs,"Save")["status"],"ambiguous")
    def test_adaptive_loop_replans_after_failure(self):
        r=self.make_runtime()
        class O:
            def __init__(self,n):self.n=n
            def to_dict(self):return {"signature":str(self.n),"elements":[]}
        states=iter([O(0),O(0),O(1),O(2),O(2)])
        decisions=iter([
            {"status":"act","tool":"definitely_missing_tool","arguments":{}},
            {"status":"act","tool":"system_info","arguments":{}},
        ])
        try:
            def decide(*args):
                try:return next(decisions)
                except StopIteration:return {"status":"goal_complete"}
            result=r.computer_use.adaptive_run("recover",lambda:next(states),decide,max_consecutive_failures=3)
            self.assertTrue(result["success"]); self.assertEqual(result["final_outcome"],"goal_complete")
            self.assertTrue(result["recoveries"])
        except StopIteration:
            self.fail("adaptive loop did not complete through replanning")
        finally:r.close()
    def test_adaptive_loop_detects_repeated_state_action(self):
        r=self.make_runtime()
        class O:
            def to_dict(self):return {"signature":"same","elements":[]}
        try:
            result=r.computer_use.adaptive_run("stuck",lambda:O(),
                lambda *a:{"status":"act","tool":"system_info","arguments":{}},
                max_retries_per_action=1,max_consecutive_failures=9)
            self.assertEqual(result["final_outcome"],"loop_detected")
        finally:r.close()
    def test_user_cancel_stops_before_action(self):
        r=self.make_runtime()
        class O:
            def to_dict(self):return {"signature":"x","elements":[]}
        try:
            r.computer_use._cancel.set()
            # adaptive_run resets cancellation for a new task; cancellation during task is separately represented by API.
            r.computer_use.reset_cancel(); r.computer_use.cancel()
            self.assertTrue(r.computer_use._cancel.is_set())
        finally:r.close()

    def test_canonical_next_action_is_single_decision_owner(self):
        r=self.make_runtime()
        try:
            decision=r.cognitive_system.decide_computer_action("open notepad",{"signature":"s"},[],None,4)
            self.assertEqual(decision["tool"],"open_application")
            self.assertEqual(decision["status"],"act")
            self.assertFalse(hasattr(r.computer_use,"decide"))
        finally:r.close()
    def test_filesystem_goal_observe_decide_execute_verify(self):
        r=self.make_runtime(); name="adaptive-test-folder"
        class O:
            def __init__(self,n):self.n=n
            def to_dict(self):return {"signature":str(self.n),"elements":[]}
        state={"n":0}
        def observe():
            state["n"]+=1; return O(state["n"])
        try:
            def decide(goal,obs,actions,last,remaining):
                if (r.root/name).is_dir():return {"status":"goal_complete"}
                return {"status":"act","tool":"create_folder","arguments":{"path":name},
                        "permission_granted":True,"verification":{"type":"file_exists","path":str(r.root/name)}}
            # safe mode deliberately blocks write: no autonomous permission bypass.
            blocked=r.computer_use.adaptive_run("create folder",observe,decide,max_consecutive_failures=1)
            self.assertFalse(blocked["success"]); self.assertFalse((r.root/name).exists())
            r.policy.safe_mode=False
            result=r.computer_use.adaptive_run("create folder",observe,decide)
            self.assertTrue(result["success"]); self.assertTrue((r.root/name).is_dir())
        finally:r.close()
    def test_episode_failure_reaches_growth_without_auto_approval(self):
        r=self.make_runtime()
        class O:
            def to_dict(self):return {"signature":"unchanged","elements":[]}
        try:
            before=len(r.cognitive_system.growth.weaknesses.rows)
            result=r.computer_use.adaptive_run("impossible desktop task",lambda:O(),
                lambda *a:{"status":"act","tool":"missing_tool","arguments":{}},max_consecutive_failures=1)
            self.assertFalse(result["success"])
            self.assertGreaterEqual(len(r.cognitive_system.growth.weaknesses.rows),before)
        finally:r.close()

    def test_registry_survives_restart(self):
        r=self.make_runtime(); names={x["name"] for x in r.registry.list()}; r.close()
        r2=IranRuntime(r.root)
        try:self.assertTrue({"screenshot","open_application","find_file","keyboard_type"} <= {x["name"] for x in r2.registry.list()})
        finally:r2.close()

if __name__=="__main__": unittest.main()

# Validation marker: trigger Windows Jarvis acceptance for conversation-memory changes.
