import unittest

from core.rule_engine import SymbolicRuleEngine


class RuleEngineTests(unittest.TestCase):
    def test_modus_ponens_and_causal_chain(self):
        engine = SymbolicRuleEngine()
        engine.add('A', 'B', .9, 'test')
        engine.add('B', 'C', .8, 'test')
        result = engine.explain(['A'], 'C')
        self.assertEqual(result['conclusion'], 'C')
        self.assertGreater(result['confidence'], .7)
        self.assertEqual(len(result['chain']), 2)

    def test_unknown_target_has_zero_confidence(self):
        result = SymbolicRuleEngine().explain(['A'], 'C')
        self.assertEqual(result['confidence'], 0.0)
        self.assertEqual(result['chain'], [])


if __name__ == '__main__':
    unittest.main()
