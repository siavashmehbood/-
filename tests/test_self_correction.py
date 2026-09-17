import json
import tempfile
import unittest
from pathlib import Path

from core.self_correction import SelfCorrectionEngine
from runtime.app import IranRuntime


class SelfCorrectionTests(unittest.TestCase):
    def test_negative_feedback_is_persistent(self):
        with tempfile.TemporaryDirectory() as d:
            engine = SelfCorrectionEngine(Path(d) / 'corrections.json')
            result = engine.record_feedback('سؤال نمونه', 'پاسخ اشتباه', 'اشتباه بود')
            self.assertTrue(result['recorded'])
            restored = SelfCorrectionEngine(Path(d) / 'corrections.json')
            rows = restored.retrieve('سؤال نمونه')
            self.assertTrue(rows)
            self.assertEqual(rows[0]['kind'], 'negative')

    def test_correction_retrieval_changes_future_answer(self):
        source = Path(__file__).resolve().parents[1] / 'config.json'
        data = json.loads(source.read_text(encoding='utf-8-sig'))
        data['memory']['db'] = 'data/test.db'
        data['runtime']['event_log'] = 'data/events.jsonl'
        data['runtime']['goals'] = 'data/goals.json'
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'data').mkdir()
            (root / 'logs').mkdir()
            (root / 'config.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            runtime = IranRuntime(root)
            try:
                first = runtime.handle('پایتخت مریخ چیه؟')
                correction = runtime.handle('اشتباهه، مریخ پایتخت ندارد')
                second = runtime.handle('پایتخت مریخ چیه؟')
                self.assertIn('پایتخت ندارد', second)
                self.assertNotEqual(first, second)
                events = runtime.events.recent(300)
                self.assertTrue(any(e.get('event') == 'self_correction_recorded' for e in events))
                self.assertTrue(any(e.get('event') == 'self_correction_applied' for e in events))
            finally:
                runtime.close()

    def test_rejected_answer_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as d:
            engine = SelfCorrectionEngine(Path(d) / 'corrections.json')
            engine.record_feedback('سؤال A', 'پاسخ قدیمی', 'بد بود')
            self.assertTrue(engine.should_avoid('سؤال A', 'پاسخ قدیمی'))
            self.assertFalse(engine.should_avoid('سؤال A', 'پاسخ کاملاً جدید'))


if __name__ == '__main__':
    unittest.main()
