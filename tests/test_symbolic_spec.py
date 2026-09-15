import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from providers.factory import create_provider


class SymbolicSpecificationTests(unittest.TestCase):
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

    def test_direct_factual_answer_is_not_internal_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            answer = runtime.handle('پایتخت ایران کجاست؟')
            self.assertIn('تهران', answer)
            self.assertNotIn('intent', answer.lower())
            self.assertNotIn('تحلیل کردم', answer)
            runtime.close()

    def test_unknown_question_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            answer = runtime.handle('دمای دقیق هسته مشتری در سال ۱۴۲۰ چقدر است؟')
            self.assertIn('UNKNOWN', answer)
            runtime.close()

    def test_external_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            create_provider({'model': {'provider': 'openai-compatible'}})


if __name__ == '__main__':
    unittest.main()
