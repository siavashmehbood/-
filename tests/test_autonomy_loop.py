import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from core.autonomy import Observation, AttentionManager


class AutonomousLoopTests(unittest.TestCase):
    def make_runtime(self, directory):
        source = Path(__file__).resolve().parents[1] / 'config.json'
        config = json.loads(source.read_text(encoding='utf-8-sig'))
        config['memory']['db'] = 'data/m.db'
        config['runtime']['event_log'] = 'data/e.jsonl'
        config['runtime']['goals'] = 'data/g.json'
        root = Path(directory)
        (root / 'data').mkdir()
        (root / 'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
        return IranRuntime(root)

    def test_attention_ranks_relevant_observation_first(self):
        manager = AttentionManager()
        low = Observation('x', 'noise', 'low', importance=.1, goal_relevance=.1)
        high = Observation('x', 'goal', 'high', importance=.9, goal_relevance=.9)
        self.assertIs(manager.rank([low, high])[0], high)

    def test_autonomous_step_emits_cycle_and_keeps_state(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            runtime.goals.add('بهبود خودمختاری IRAN')
            result = runtime.autonomous_step()
            self.assertEqual(result['cycle_id'], 1)
            self.assertEqual(result['active_goal'], 'بهبود خودمختاری IRAN')
            self.assertEqual(result['status'], 'idle')
            events = runtime.events.recent(20)
            self.assertTrue(any(e.get('event') == 'autonomous_cycle' for e in events))
            runtime.close()


if __name__ == '__main__':
    unittest.main()
    def test_autonomy_state_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            runtime.goals.add('حفظ وضعیت شناختی')
            runtime.autonomous_step()
            first_id = runtime.autonomy.state.cycle_id
            runtime.close()
            runtime2 = IranRuntime(Path(directory))
            self.assertEqual(runtime2.autonomy.state.cycle_id, first_id)
            runtime2.close()
