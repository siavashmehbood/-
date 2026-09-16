"""Reasoning contracts: backward chaining and contradiction detection.

The mission requires the reasoning layer to support inference chains, explainability,
uncertainty handling and contradiction detection. The engine had forward chaining and
an `explain` wrapper; backward chaining and contradiction detection were absent.

Backward chaining matters because `infer` only reports whether forward chaining
happened to reach a target. Checking a goal against the rules before answering needs the
opposite question: which rules could derive it, and are their antecedents themselves
derivable?
"""
import unittest

from core.rule_engine import SymbolicRuleEngine


class BackwardChainingTests(unittest.TestCase):
    def setUp(self):
        self.engine = SymbolicRuleEngine()

    def test_fact_is_proved_directly(self):
        result = self.engine.prove(['باران'], 'باران')
        self.assertTrue(result['proved'])
        self.assertEqual(result['confidence'], 1.0)

    def test_single_rule_is_proved(self):
        self.engine.add('باران', 'خیس', confidence=0.9)
        result = self.engine.prove(['باران'], 'خیس')
        self.assertTrue(result['proved'])
        self.assertAlmostEqual(result['confidence'], 0.9, places=4)
        self.assertTrue(any('باران -> خیس' in step for step in result['proof']))

    def test_multi_hop_proof_multiplies_confidence(self):
        self.engine.add('الف', 'ب', confidence=0.5)
        self.engine.add('ب', 'پ', confidence=0.5)
        result = self.engine.prove(['الف'], 'پ')
        self.assertTrue(result['proved'])
        self.assertAlmostEqual(result['confidence'], 0.25, places=4)
        # The proof must be ordered from the facts toward the target.
        self.assertEqual(len(result['proof']), 3)

    def test_unprovable_target_reports_unresolved_antecedent(self):
        self.engine.add('وضعیت نامشخص', 'هشدار')
        result = self.engine.prove(['مورد دیگر'], 'هشدار')
        self.assertFalse(result['proved'])
        self.assertEqual(result['confidence'], 0.0)
        # A failure must be diagnosable, not just "not proved".
        self.assertEqual(result['unresolved'], ['وضعیت نامشخص'])

    def test_most_confident_proof_wins(self):
        self.engine.add('الف', 'هدف', confidence=0.4)
        self.engine.add('ب', 'هدف', confidence=0.9)
        result = self.engine.prove(['الف', 'ب'], 'هدف')
        self.assertTrue(result['proved'])
        self.assertAlmostEqual(result['confidence'], 0.9, places=4)

    def test_cyclic_rules_terminate(self):
        # A -> B, B -> A would recurse forever without a visiting guard.
        self.engine.add('الف', 'ب')
        self.engine.add('ب', 'الف')
        result = self.engine.prove(['مورد دیگر'], 'ب')
        self.assertFalse(result['proved'])

    def test_depth_limit_is_respected(self):
        self.engine.add('الف', 'ب')
        self.engine.add('ب', 'پ')
        self.engine.add('پ', 'ت')
        shallow = self.engine.prove(['الف'], 'ت', max_depth=1)
        deep = self.engine.prove(['الف'], 'ت', max_depth=5)
        self.assertFalse(shallow['proved'])
        self.assertTrue(deep['proved'])

    def test_prove_does_not_mutate_facts_or_rules(self):
        self.engine.add('الف', 'ب')
        facts = ['الف']
        self.engine.prove(facts, 'ب')
        self.assertEqual(facts, ['الف'])
        self.assertEqual(len(self.engine.rules), 1)


class ContradictionDetectionTests(unittest.TestCase):
    def setUp(self):
        self.engine = SymbolicRuleEngine()

    def test_direct_positive_and_negative_is_detected(self):
        found = self.engine.contradictions(['باران', 'not:باران'])
        self.assertTrue(found)
        literal = [f for f in found if f['literal'] == 'باران']
        self.assertTrue(literal)
        self.assertEqual(literal[0]['negation_evidence'], 'not:باران')

    def test_derived_positive_against_direct_negative_is_detected(self):
        # The positive is not stated, only derivable; the contradiction must still be found.
        self.engine.add('ابر سنگین', 'باران', confidence=0.9)
        found = self.engine.contradictions(['ابر سنگین', 'not:باران'], target='باران')
        self.assertTrue(found)
        self.assertEqual(found[0]['literal'], 'باران')
        self.assertAlmostEqual(found[0]['positive_confidence'], 0.9, places=4)

    def test_no_contradiction_on_consistent_facts(self):
        self.engine.add('ابر سنگین', 'باران')
        found = self.engine.contradictions(['ابر سنگین'], target='باران')
        self.assertEqual(found, [])

    def test_negation_without_positive_is_not_a_contradiction(self):
        found = self.engine.contradictions(['not:باران'], target='باران')
        self.assertEqual(found, [])


if __name__ == '__main__':
    unittest.main()
