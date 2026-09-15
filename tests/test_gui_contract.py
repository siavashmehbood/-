import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime


class GuiContractTests(unittest.TestCase):
    def make_runtime(self, directory):
        source = Path(__file__).resolve().parents[1] / 'config.json'
        config = json.loads(source.read_text(encoding='utf-8-sig'))
        config['memory']['db'] = 'data/test.db'
        config['runtime']['event_log'] = 'data/events.jsonl'
        config['runtime']['goals'] = 'data/goals.json'
        root = Path(directory)
        (root / 'data').mkdir()
        (root / 'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
        return IranRuntime(root)

    def test_early_response_has_mode_for_gui(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            runtime.handle('پایتخت ایران کجاست؟')
            rows = [e for e in runtime.events.recent(50) if e.get('event') == 'response_generated']
            self.assertTrue(rows[-1]['data'].get('mode'))
            runtime.close()

    def test_gui_contains_cognitive_workspace_surfaces(self):
        source = Path(__file__).resolve().parents[1] / 'gui.py'
        text = source.read_text(encoding='utf-8')
        for marker in ('وضعیت شناختی', 'آخرین رویدادها', 'run_benchmark', 'show_trace', 'quality'):
            self.assertIn(marker, text)


if __name__ == '__main__':
    unittest.main()
