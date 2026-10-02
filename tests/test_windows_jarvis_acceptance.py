"""Final Windows acceptance: real app, screen, system, and canonical action path."""
import os, tempfile, unittest
from pathlib import Path
from tools.desktop import DesktopTools
from runtime.app import IranRuntime
import json

@unittest.skipUnless(os.name=="nt","Windows acceptance suite")
class WindowsJarvisAcceptance(unittest.TestCase):
    def test_calculator_real_process(self):
        with tempfile.TemporaryDirectory() as d:
            result=DesktopTools(d).open_application("calculator")
            self.assertTrue(result["running"]); self.assertGreater(result["pid"],0)
    def test_real_screenshot_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            result=DesktopTools(d).screenshot()
            self.assertTrue(result["exists"]); self.assertGreater(result["width"],0); self.assertGreater(result["height"],0)
    def test_canonical_natural_request_executes_and_verifies_real_app(self):
        root=Path(tempfile.mkdtemp()); cfg=json.loads(Path("config.json").read_text(encoding="utf-8-sig"))
        cfg["memory"]["db"]="data/test.db"; cfg["runtime"]["event_log"]="data/events.jsonl"; cfg["runtime"]["goals"]="data/goals.json"
        (root/"data").mkdir(); (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
        runtime=IranRuntime(root)
        try:
            answer=runtime.handle("open calculator")
            outcome=runtime.cognitive_system.last_output.get("computer_action",{})
            self.assertEqual(answer,"انجام شد.")
            self.assertEqual(outcome.get("tool"),"open_application")
            self.assertTrue(outcome.get("success"))
            self.assertTrue(outcome.get("verification",{}).get("verified"))
        finally: runtime.close()

    def test_real_multistep_notepad_observe_type_verify(self):
        root=Path(tempfile.mkdtemp()); cfg=json.loads(Path("config.json").read_text(encoding="utf-8-sig"))
        cfg["memory"]["db"]="data/test.db"; cfg["runtime"]["event_log"]="data/events.jsonl"; cfg["runtime"]["goals"]="data/goals.json"
        (root/"data").mkdir(); (root/"config.json").write_text(json.dumps(cfg),encoding="utf-8")
        runtime=IranRuntime(root); from tools.desktop import DesktopTools,WindowsDesktop,InputController,ScreenObserver
        observer=ScreenObserver(DesktopTools(root),WindowsDesktop(root),InputController()); sentence="IRAN autonomous computer use test"
        stage={"n":0}
        def decide(goal,obs,actions,last,remaining):
            n=stage["n"]; stage["n"]+=1
            if n==0:return {"status":"act","tool":"open_application","arguments":{"name":"notepad"},"verification":{"type":"element_present","label":"Notepad"}}
            if n==1:
                windows=[w for w in obs.get("visible_windows",[]) if "notepad" in str(w.get("title","")).lower()]
                if not windows:return {"status":"safe_stop"}
                return {"status":"act","tool":"focus_window","arguments":{"hwnd":windows[0]["hwnd"]},"permission_granted":True,"verification":{"type":"window_title","contains":"Notepad"}}
            if n==2:
                windows=[w for w in obs.get("visible_windows",[]) if "notepad" in str(w.get("title","")).lower()]
                if not windows:return {"status":"safe_stop"}
                return {"status":"act","tool":"uia_type_text","arguments":{"hwnd":windows[0]["hwnd"],"text":sentence},"permission_granted":True}
            if n==3:
                windows=[w for w in obs.get("visible_windows",[]) if "notepad" in str(w.get("title","")).lower()]
                if not windows:return {"status":"safe_stop"}
                return {"status":"act","tool":"uia_document_text","arguments":{"hwnd":windows[0]["hwnd"]}}
            return {"status":"goal_complete"}
        try:
            result=runtime.computer_use.adaptive_run("Open Notepad and type: "+sentence,lambda:observer.observe(capture=False),decide,timeout_seconds=30,max_consecutive_failures=4)
            self.assertTrue(any(a["tool"]=="uia_type_text" for a in result["actions"]))
            observed=[a for a in result["actions"] if a["tool"]=="uia_document_text"]
            self.assertTrue(observed)
            self.assertIn(sentence,observed[-1]["outcome"]["execution"]["result"]["text"])
            self.assertTrue(result["success"])
        finally: runtime.close()

    def test_window_recovery_real_focus(self):
        from tools.desktop import WindowsDesktop
        with tempfile.TemporaryDirectory() as d:
            desk=DesktopTools(d); win=WindowsDesktop(d); desk.open_application("notepad")
            import time; time.sleep(1)
            found=win.find_window("Notepad")
            self.assertTrue(found["matches"])
            target=found["matches"][0]; win.focus(target["hwnd"]); time.sleep(.2)
            self.assertIn("notepad",win.active_window()["title"].lower())

    def test_real_system_information(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("Windows",DesktopTools(d).system_info()["platform"])

if __name__=="__main__": unittest.main()
