import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from tests.chatgpt_test_helper import mark_chatgpt_correct


class SymbolicExpansionTests(unittest.TestCase):
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

    def test_local_facts_cover_more_than_one_domain(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            self.assertIn('پاریس', runtime.handle('پایتخت فرانسه کجاست؟'))
            self.assertIn('هفت', runtime.handle('هفته چند روز دارد؟'))
            self.assertIn('۱۰۰', runtime.handle('آب در چند درجه می‌جوشد؟'))
            runtime.close()

    def test_positive_feedback_is_persisted_and_acknowledged(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            runtime.handle('پایتخت ایران کجاست؟')
            answer = runtime.handle('این پاسخ درست بود.')
            self.assertIn('بازخورد', answer)
            pending = runtime.learning_pending()
            self.assertTrue(pending)
            for proposal in list(pending):
                mark_chatgpt_correct(runtime, proposal["proposal_id"], "تأیید آزمون: بازخورد مثبت و اثر آن معتبر است.")
                runtime.approve_learning(proposal["proposal_id"])
            self.assertGreaterEqual(runtime.learning.stats()['experiences'], 1)
            self.assertIn('learning_update', [item['event'] for item in runtime.events.recent(50)])
            runtime.close()


if __name__ == '__main__':
    unittest.main()
