import json
import tempfile
import unittest
from pathlib import Path

from core.answer_generator import AnswerGenerator
from core.contracts import FinalAnswer, ParsedInput
from core.response_engine import LocalResponseEngine
from knowledge.knowledge_graph import KnowledgeGraph
from runtime.app import IranRuntime


class CanonicalContractTests(unittest.TestCase):
    def test_answer_generator_returns_typed_final_answer(self):
        engine = AnswerGenerator(LocalResponseEngine())
        result = engine.generate('پایتخت ایران کجاست؟', ParsedInput('x', 'x'), {'confidence': .9}, [], {})
        self.assertIsInstance(result, FinalAnswer)
        self.assertEqual(result.mode, 'DIRECT_FACT')
        self.assertIn('تهران', result.text)
        self.assertNotIn('hypotheses', result.text)

    def test_knowledge_graph_is_used_by_generator(self):
        with tempfile.TemporaryDirectory() as directory:
            graph = KnowledgeGraph(Path(directory) / 'knowledge.json')
            graph.add_fact('ایران', 'پایتخت', 'تهران', .99, 'test')
            engine = AnswerGenerator(LocalResponseEngine(), graph)
            result = engine.generate('پایتخت ایران کجاست؟', {}, {}, [], {})
            self.assertEqual(result.text, 'تهران')

    def test_runtime_seeds_local_knowledge_and_emits_answer_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(__file__).resolve().parents[1] / 'config.json'
            config = json.loads(source.read_text(encoding='utf-8-sig'))
            config['memory']['db'] = 'data/test.db'
            config['runtime']['event_log'] = 'data/events.jsonl'
            config['runtime']['goals'] = 'data/goals.json'
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
            runtime = IranRuntime(root)
            self.assertEqual(runtime.knowledge.resolve('ایران', 'پایتخت')['object'], 'تهران')
            runtime.handle('پایتخت ایران کجاست؟')
            events = runtime.events.recent(20)
            generated = [e for e in events if e['event'] == 'response_generated'][-1]
            self.assertEqual(generated['data']['mode'], 'DIRECT_FACT')
            runtime.close()


if __name__ == '__main__':
    unittest.main()
