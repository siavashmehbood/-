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

    def test_real_system_information(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("Windows",DesktopTools(d).system_info()["platform"])

if __name__=="__main__": unittest.main()
