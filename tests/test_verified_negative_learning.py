import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from tools.registry import Tool


class VerifiedNegativeLearningTests(unittest.TestCase):

    def test_decision_engine_consumes_verified_experience(self):
        from core.decision import DecisionEngine
        from core.prediction import Prediction
        engine = DecisionEngine()
        predictions = [
            Prediction('a', 'ok', .2, .7, .55, 1, .9, []),
            Prediction('b', 'ok', .2, .7, .55, 1, .9, []),
        ]
        evidence = {'ranked': [
            {'action': 'a', 'score': .0, 'verified_samples': 3},
            {'action': 'b', 'score': 1.0, 'verified_samples': 3},
        ]}
        decision = engine.choose(['a', 'b'], predictions, 0.0, evidence)
        self.assertEqual(decision.chosen, 'b')
        self.assertTrue(any('verified experience=1.00' in r for r in decision.options[0].rationale))

    def test_planner_receives_verified_experience_as_strategy(self):
        from planning.planner import Planner
        plan = Planner().build('repeat task', experience={
            'selected': 'good_action',
            'ranked': [{'action': 'good_action', 'verified_samples': 3, 'score': 1.0}],
        })
        self.assertEqual(plan.strategy, 'experience-guided:good_action')
        self.assertIn('verified-experience-selected=good_action', plan.assumptions)
        self.assertIn('good_action', plan.steps[0].success_criteria)

    def test_verified_experience_promotes_and_transfers_a_skill_to_a_new_goal(self):
        source = Path(__file__).resolve().parents[1] / 'config.json'
        data = json.loads(source.read_text(encoding='utf-8-sig'))
        data['memory']['db'] = 'data/test.db'
        data['runtime']['event_log'] = 'data/events.jsonl'
        data['runtime']['goals'] = 'data/goals.json'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'data').mkdir()
            (root / 'config.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            runtime = IranRuntime(root)
            runtime.registry.register(Tool('good_action', 'good', lambda: 'correct', safe=True))
            try:
                first = runtime.execute_verified_goal('backup project files alpha', 'good_action', None, 'correct')
                second = runtime.execute_verified_goal('backup project files beta', 'good_action', None, 'correct')
                self.assertTrue(first['primary']['success'] and second['primary']['success'])
                self.assertTrue(runtime.skills.skills)
                third = runtime.execute_verified_goal('backup project files gamma', 'good_action', None, 'correct')
                self.assertTrue(third['primary']['success'])
                self.assertTrue(third['plan'].strategy.startswith('skill-transfer:'))
                transfer_events = [e for e in runtime.events.recent(300) if e.get('event') == 'skill_transfer_consulted']
                self.assertTrue(transfer_events)
                self.assertTrue(transfer_events[-1]['data']['applied'])
            finally:
                runtime.close()

    def test_verified_failure_becomes_negative_evidence_for_next_decision(self):
        source = Path(__file__).resolve().parents[1] / 'config.json'
        data = json.loads(source.read_text(encoding='utf-8-sig'))
        data['memory']['db'] = 'data/test.db'
        data['runtime']['event_log'] = 'data/events.jsonl'
        data['runtime']['goals'] = 'data/goals.json'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'config.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            runtime = IranRuntime(root)
            runtime.registry.register(Tool('bad_action', 'bad', lambda: 'wrong', safe=True))
            runtime.registry.register(Tool('good_action', 'good', lambda: 'correct', safe=True))
            try:
                first = runtime.execute_verified_goal(
                    'learn from failure demo', 'bad_action', 'good_action', 'correct')
                self.assertTrue(first['alternative']['success'])
                records = runtime.outcome_learning.retrieve_context('learn from failure demo', 'task', 10)
                bad = [r for r in records if r['action'] == 'bad_action']
                good = [r for r in records if r['action'] == 'good_action']
                self.assertTrue(bad and bad[-1]['verified'] and bad[-1]['score'] == 0.0)
                self.assertTrue(good and good[-1]['verified'] and good[-1]['score'] == 1.0)
                episode_id = first['task']['task_id']
                trace = runtime.outcome_learning.episode_trace(episode_id)
                self.assertEqual([row['phase'] for row in trace], ['primary', 'alternative'])
                self.assertEqual([row['attempt'] for row in trace], [1, 2])
                self.assertTrue(all(row['episode_id'] == episode_id for row in trace))

                second = runtime.execute_verified_goal(
                    'learn from failure demo', 'bad_action', 'good_action', 'correct')
                self.assertTrue(second['primary']['success'])
                reused = [e for e in runtime.events.recent(200)
                           if e.get('event') == 'strategy_reused'
                           and e.get('data', {}).get('source') == 'outcome_backed_learning']
                self.assertTrue(reused)
                self.assertEqual(reused[-1]['data']['selected'], 'good_action')
            finally:
                runtime.close()


if __name__ == '__main__':
    unittest.main()
