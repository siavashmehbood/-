import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime


class BenchmarkGeneralizationTests(unittest.TestCase):
    def make_runtime(self, directory):
        source=Path(__file__).resolve().parents[1]/'config.json'
        config=json.loads(source.read_text(encoding='utf-8-sig'))
        config['memory']['db']='data/m.db'; config['runtime']['event_log']='data/e.jsonl'; config['runtime']['goals']='data/g.json'
        root=Path(directory); (root/'data').mkdir(); (root/'config.json').write_text(json.dumps(config,ensure_ascii=False),encoding='utf-8')
        return IranRuntime(root)

    def test_factual_paraphrase_uses_knowledge_not_exact_question(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime=self.make_runtime(directory)
            answer=runtime.handle('مرکز سیاسی کشور ایران چیست؟')
            self.assertIn('تهران', answer)
            runtime.close()

    def test_unknown_variant_does_not_become_fact(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime=self.make_runtime(directory)
            answer=runtime.handle('در سال ۱۴۲۰ دمای دقیق هسته مشتری چند خواهد بود؟')
            self.assertIn('UNKNOWN', answer)
            runtime.close()


if __name__ == '__main__':
    unittest.main()
