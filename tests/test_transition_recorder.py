import unittest
from core.world.transition import TransitionRecorder

class FakeWorld:
    def __init__(self):
        self.items = []
    def observe(self, item):
        self.items.append(item)

class TransitionRecorderTests(unittest.TestCase):
    def test_records_verified_state_transition(self):
        world = FakeWorld()
        recorder = TransitionRecorder(world)
        t = recorder.record(
            'task-1',
            {'action_id': 'a1', 'tool_name': 'time_now'},
            {'summary': 'clock observed'},
            {'success': True, 'reason': 'evidence-backed'},
            {'phase': 'ready'},
        )
        self.assertEqual(t.task_id, 'task-1')
        self.assertTrue(t.verification['success'])
        self.assertEqual(t.state_before['phase'], 'ready')
        self.assertTrue(t.state_after['last_verified'])
        self.assertEqual(len(world.items), 1)

if __name__ == '__main__':
    unittest.main()
