import json
import tempfile
import unittest
from pathlib import Path

from core.cognitive_controller import CognitiveController, GlobalWorkspace, ProceduralLearner


class ControllerTests(unittest.TestCase):
    def test_attention_broadcast_prefers_salient_relevant_item(self):
        ws = GlobalWorkspace(capacity=10, broadcast_limit=2)
        ws.add('پایتخت ایران تهران', 'knowledge', .95, .95)
        ws.add('آب و هوا', 'memory', .20, .40)
        rows = ws.attend('پایتخت ایران')
        self.assertEqual(rows[0].content, 'پایتخت ایران تهران')

    def test_procedure_learning_reinforces_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            learner = ProceduralLearner(Path(tmp) / 'procedures.json')
            p = learner.record('question', ['understand', 'retrieve', 'answer'], True, .9)
            self.assertGreater(p.value, .5)
            learner2 = ProceduralLearner(Path(tmp) / 'procedures.json')
            self.assertEqual(learner2.best('question').steps, ['understand', 'retrieve', 'answer'])

    def test_controller_cycle_is_offline_and_tracks_self(self):
        class State:
            intent = 'question'
            goal = 'پایتخت ایران'
            evidence = [{'content': 'ایران پایتخت تهران', 'source': 'knowledge', 'confidence': .99, 'kind': 'fact'}]
            contradictions = []
            plan = ['understand', 'retrieve', 'answer', 'verify']
            confidence = .9

        class Runtime:
            nars = object()
            knowledge = object()
            atomspace = object()
            cognitive_core = object()
            planner = object()

        with tempfile.TemporaryDirectory() as tmp:
            controller = CognitiveController(Runtime(), Path(tmp) / 'procedures.json')
            cycle = controller.cycle('پایتخت ایران چیست؟', State(), 'تهران')
            self.assertEqual(cycle['selected'], 'answer_with_evidence')
            controller.learn(State(), 'تهران', {'passed': True, 'score': 1.0})
            self.assertEqual(controller.self_model.successful_cycles, 1)


if __name__ == '__main__':
    unittest.main()
