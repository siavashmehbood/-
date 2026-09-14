import tempfile
import unittest
from pathlib import Path
from runtime.app import IranRuntime

class RuntimeTests(unittest.TestCase):
    def make_root(self, tmp):
        root = Path(tmp)
        config = ('{"name":"ایران","version":"test","model":{"provider":"iran"},'
                  '"memory":{"db":"data.db","max_history":4,"search_limit":4},'
                  '"security":{"safe_mode":true,"allow_shell":false,"allow_network_tools":true},'
                  '"self_improvement":{"enabled":true,"sandbox":"sandbox","auto_deploy":false,"require_tests":true},'
                  '"runtime":{"event_log":"events.jsonl","goals":"goals.json"}}')
        (root / 'config.json').write_text(config, encoding='utf-8')
        return root

    def test_runtime_boots_and_handles(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = IranRuntime(self.make_root(tmp))
            self.assertIn('ایران', runtime.handle('سلام'))
            self.assertTrue(runtime.health()['ok'])
            runtime.close()

    def test_runtime_tool_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = IranRuntime(self.make_root(tmp))
            self.assertIn('زمان سیستم', runtime.handle('ساعت الان'))
            runtime.close()

    def test_agent_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = IranRuntime(self.make_root(tmp))
            result = runtime.orchestrator.loop.run('سلام')
            self.assertEqual(result.status, 'completed')
            self.assertEqual(result.attempts, 1)
            runtime.close()

if __name__ == '__main__':
    unittest.main()

