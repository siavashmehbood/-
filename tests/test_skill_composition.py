import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from tools.registry import Tool


class SkillCompositionIntegrationTests(unittest.TestCase):
    def _runtime(self, directory):
        source = Path(__file__).resolve().parents[1] / 'config.json'
        data = json.loads(source.read_text(encoding='utf-8-sig'))
        data['memory']['db'] = 'data/test.db'
        data['runtime']['event_log'] = 'data/events.jsonl'
        data['runtime']['goals'] = 'data/goals.json'
        root = Path(directory)
        (root / 'data').mkdir()
        (root / 'config.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return IranRuntime(root)

    def test_composes_two_verified_skills_into_new_goal(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(directory)
            runtime.registry.register(Tool('prepare_step', 'prepare', lambda: 'prepared', safe=True))
            runtime.registry.register(Tool('finish_step', 'finish', lambda: 'finished', safe=True))
            goal = 'prepare then finish composed demo'
            runtime.skills.upsert(
                name='prepare-skill', description='prepare learned step', domain='task',
                goal_patterns=[goal], procedure={'steps': [{'action': 'prepare_step', 'expected_effect': 'prepared'}]},
                preconditions=[], confidence=.9)
            runtime.skills.upsert(
                name='finish-skill', description='finish learned step', domain='task',
                goal_patterns=[goal], procedure={'steps': [{'action': 'finish_step', 'expected_effect': 'finished'}]},
                preconditions=[], confidence=.9)

            result = runtime.execute_verified_goal(goal, 'prepare_step', expected_effect='finished')
            self.assertTrue(result['success'])
            self.assertEqual(result['plan_strategy'], 'skill-composition')
            self.assertEqual(len(result['composition']['skill_ids']), 2)
            self.assertEqual([x['step']['action'] for x in result['steps']], ['prepare_step', 'finish_step'])
            self.assertEqual(len(runtime.skills.compositions), 1)
            self.assertTrue(runtime.skills.retrieve_compositions(goal))
            self.assertTrue(all(x['verification'].success for x in result['steps']))
            events = [item['event'] for item in runtime.events.recent(120)]
            self.assertIn('skill_composition_step', events)
            self.assertIn('skill_composition_completed', events)
            runtime.close()

    def test_hierarchical_skill_can_be_recomposed_with_new_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(directory)
            for name, result in [('step_a','a'), ('step_b','b'), ('step_c','c')]:
                runtime.registry.register(Tool(name, name, lambda value=result: value, safe=True))
            goal_ab = 'build layered ab behavior'
            runtime.skills.upsert(name='skill-a', description='a', domain='task', goal_patterns=[goal_ab],
                                  procedure={'steps':[{'action':'step_a','expected_effect':'a'}]}, preconditions=[], confidence=.9)
            runtime.skills.upsert(name='skill-b', description='b', domain='task', goal_patterns=[goal_ab],
                                  procedure={'steps':[{'action':'step_b','expected_effect':'b'}]}, preconditions=[], confidence=.9)
            first = runtime.execute_verified_goal(goal_ab, 'step_a', expected_effect='b')
            self.assertTrue(first['success'])
            higher = first['higher_order_skill']
            self.assertTrue(higher['is_composite'])
            self.assertEqual(higher['composition_level'], 1)
            self.assertEqual(set(higher['source_skill_ids']), set(first['composition']['skill_ids']))

            goal_abc = 'extend layered ab behavior with c'
            runtime.skills.upsert(name='skill-c', description='c', domain='task', goal_patterns=[goal_abc],
                                  procedure={'steps':[{'action':'step_c','expected_effect':'c'}]}, preconditions=[], confidence=.9)
            higher['goal_patterns'] = [goal_abc]
            runtime.skills._save()
            second = runtime.execute_verified_goal(goal_abc, 'step_a', expected_effect='c')
            self.assertTrue(second['success'])
            self.assertGreaterEqual(len(second['composition']['skill_ids']), 2)
            self.assertEqual(second['higher_order_skill']['composition_level'], 2)
            self.assertIn(higher['skill_id'], second['composition']['skill_ids'])
            c_id = next(x['skill_id'] for x in runtime.skills.skills if x['name']=='skill-c')
            self.assertIn(c_id, second['composition']['skill_ids'])
            self.assertEqual(len(runtime.skills.compositions), 2)
            runtime.close()

    def test_composition_stops_on_failed_step(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(directory)
            runtime.registry.register(Tool('first_step', 'first', lambda: 'ok', safe=True))
            runtime.registry.register(Tool('broken_step', 'broken', lambda: 'wrong', safe=True))
            goal = 'first then broken composed demo'
            runtime.skills.upsert(name='first-skill', description='first', domain='task', goal_patterns=[goal],
                                  procedure={'steps': [{'action': 'first_step', 'expected_effect': 'ok'}]}, preconditions=[], confidence=.9)
            runtime.skills.upsert(name='broken-skill', description='broken', domain='task', goal_patterns=[goal],
                                  procedure={'steps': [{'action': 'broken_step', 'expected_effect': 'expected'}]}, preconditions=[], confidence=.9)
            result = runtime.execute_verified_goal(goal, 'first_step', expected_effect='expected')
            self.assertFalse(result['success'])
            self.assertEqual(len(result['steps']), 2)
            self.assertTrue(result['steps'][0]['verification'].success)
            self.assertFalse(result['steps'][1]['verification'].success)
            self.assertIn('skill_composition_failed', [item['event'] for item in runtime.events.recent(120)])
            runtime.close()


if __name__ == '__main__':
    unittest.main()

