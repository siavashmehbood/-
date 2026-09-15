import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime


class AutonomyPersistenceTests(unittest.TestCase):
    def make_runtime(self, directory):
        source = Path(__file__).resolve().parents[1] / "config.json"
        config = json.loads(source.read_text(encoding="utf-8-sig"))
        config["memory"]["db"] = "data/m.db"
        config["runtime"]["event_log"] = "data/e.jsonl"
        config["runtime"]["goals"] = "data/g.json"
        root = Path(directory)
        (root / "data").mkdir(exist_ok=True)
        (root / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return IranRuntime(root)

    def test_autonomy_state_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.make_runtime(directory)
            first.goals.add("پایش پروژه")
            first.autonomous_step()
            first.close()
            second = self.make_runtime(directory)
            self.assertGreaterEqual(second.autonomy.state.cycle_id, 1)
            self.assertEqual(second.autonomy.state.active_goal, "پایش پروژه")
            second.close()


if __name__ == "__main__":
    unittest.main()
