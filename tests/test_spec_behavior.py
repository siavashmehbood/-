import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from tools.registry import Tool


class SpecificationBehaviorTests(unittest.TestCase):
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

    def test_question_does_not_create_false_like_fact(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            runtime.handle('من برنامه‌نویسی را دوست دارم.')
            runtime.handle('من چی دوست دارم؟')
            facts = runtime.user_model.facts(predicate='likes', limit=20)
            values = [fact['object'].replace('\u200c', ' ') for fact in facts]
            self.assertEqual(values, ['برنامه نویسی'])
            runtime.close()

    def test_current_belief_preserves_history_and_prefers_recent_fact(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            runtime.handle('من علی هستم.')
            runtime.handle('من رضا هستم.')
            history = runtime.user_model.facts(predicate='name', limit=20)
            self.assertEqual({fact['object'] for fact in history}, {'علی', 'رضا'})
            self.assertEqual(runtime.user_model.current_belief('name')[0]['object'], 'رضا')
            self.assertIn('name', runtime.user_model.contradictions())
            runtime.close()

    def test_continuation_keeps_resolved_topic(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            runtime.handle('موضوع اصلی ما معماری شناختی ایران است.')
            runtime.handle('همون قبلی رو ادامه بده.')
            answer = runtime.handle('همونو بیشتر توضیح بده.')
            self.assertIn('معماری شناختی ایران', answer)
            runtime.close()

    def test_unknown_question_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            answer = runtime.handle('دمای دقیق هسته مشتری در سال ۱۴۲۰ چند است؟')
            self.assertIn('UNKNOWN', answer)
            self.assertNotIn('حتماً', answer)
            runtime.close()

    def test_verified_outcome_changes_future_tool_preference(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            runtime.registry.register(Tool('bad_tool', 'bad', lambda: 'wrong', safe=True))
            runtime.registry.register(Tool('good_tool', 'good', lambda: 'correct', safe=True))
            first = runtime.handle('/run first demo --tool bad_tool --expected correct --alternative good_tool')
            self.assertIn('task=success', first)
            for proposal in list(runtime.learning_pending()):
                runtime.approve_learning(proposal["proposal_id"])
            second = runtime.handle('/run second demo --tool bad_tool --expected correct --alternative good_tool')
            self.assertIn('task=success', second)
            events = [item['event'] for item in runtime.events.recent(100)]
            self.assertIn('strategy_reused', events)
            self.assertEqual(runtime.goals.list(status='completed')[-1]['title'], 'second demo')
            runtime.close()


if __name__ == '__main__':
    unittest.main()
