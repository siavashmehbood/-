import os, tempfile, unittest
from pathlib import Path
from tools.desktop import DesktopTools

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
    def test_real_system_information(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("Windows",DesktopTools(d).system_info()["platform"])

if __name__=="__main__": unittest.main()
