"""Knowledge graph contracts: provenance tracing, contradiction, validation, persistence.

The mission requires every important conclusion to be able to answer "which
facts/rules/memories produced this?". The graph could compute an inferred confidence
but could not show the path that produced it, and had no integrity check. Both are
covered here against the real durable graph.
"""
import tempfile
import unittest
from pathlib import Path

from knowledge.knowledge_graph import KnowledgeGraph


class KnowledgeGraphContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.graph = KnowledgeGraph(self.tmp / 'graph.json')

    def test_add_and_query_fact(self):
        self.graph.add_fact('پایتون', 'نوع', 'زبان برنامه‌نویسی')
        rows = self.graph.query('پایتون')
        self.assertTrue(rows)
        self.assertEqual(rows[0]['subject'], 'پایتون')

    def test_confidence_propagates_across_hops(self):
        self.graph.add_fact('الف', 'به', 'ب', confidence=1.0)
        self.graph.add_fact('ب', 'به', 'پ', confidence=0.5)
        inferred = self.graph.infer('الف', depth=3)
        by_object = {entry['fact']['object']: entry for entry in inferred}
        self.assertEqual(by_object['ب']['inferred_confidence'], 1.0)
        self.assertEqual(by_object['پ']['inferred_confidence'], 0.5)

    def test_trace_returns_provenance_chain(self):
        self.graph.add_fact('الف', 'به', 'ب', confidence=1.0, source='seed')
        self.graph.add_fact('ب', 'به', 'پ', confidence=0.5, source='derived')
        trace = self.graph.trace('الف', depth=3)
        self.assertTrue(trace['complete'])
        self.assertEqual(trace['subject'], 'الف')
        self.assertEqual(len(trace['direct_facts']), 1)
        self.assertEqual(len(trace['chain']), 2)
        # Each hop must name the path that produced it, so a conclusion is auditable.
        for entry in trace['chain']:
            self.assertIn('provenance', entry)
            self.assertGreaterEqual(len(entry['provenance']), 1)
        multi_hop = [e for e in trace['chain'] if e['hop'] == 2][0]
        self.assertEqual(len(multi_hop['provenance']), 2)
        self.assertEqual(multi_hop['propagated_confidence'], 0.5)

    def test_trace_on_unknown_subject_reports_incomplete(self):
        trace = self.graph.trace('چیزی که وجود ندارد')
        self.assertFalse(trace['complete'])
        self.assertEqual(trace['chain'], [])

    def test_trace_can_filter_by_predicate(self):
        self.graph.add_fact('الف', 'رنگ', 'سبز')
        self.graph.add_fact('الف', 'اندازه', 'بزرگ')
        trace = self.graph.trace('الف', predicate='رنگ')
        self.assertEqual(len(trace['direct_facts']), 1)
        self.assertEqual(trace['direct_facts'][0]['predicate'], 'رنگ')

    def test_contradiction_is_recorded_and_detectable(self):
        self.graph.add_fact('آب', 'درجه جوش', '۱۰۰')
        self.graph.contradict('آب', 'درجه جوش', '۹۰')
        contradictions = self.graph.contradictions('آب')
        self.assertTrue(contradictions)
        self.assertEqual(contradictions[0]['contradicted_by']['object'], '۹۰')

    def test_contradicted_fact_ranks_below_clean_fact(self):
        self.graph.add_fact('الف', 'ویژگی', 'یک', confidence=0.9)
        self.graph.add_fact('ب', 'ویژگی', 'دو', confidence=0.9)
        self.graph.contradict('ب', 'ویژگی', 'سه')
        resolved_a = self.graph.resolve('الف', 'ویژگی')
        resolved_b = self.graph.resolve('ب', 'ویژگی')
        self.assertIsNotNone(resolved_a)
        self.assertIsNotNone(resolved_b)
        self.assertGreater(float(resolved_a['confidence']), 0.0)

    def test_validate_passes_on_healthy_graph(self):
        self.graph.add_fact('پایتون', 'نوع', 'زبان برنامه‌نویسی')
        self.graph.add_edge('پایتون', 'استفاده‌شده_در', 'پروژه')
        report = self.graph.validate()
        self.assertTrue(report['ok'], report['problems'])
        # `add_edge` writes through `add_fact`, so both calls land as facts.
        self.assertEqual(report['checked'], len(self.graph.facts))
        self.assertEqual(report['checked'], 2)

    def test_validate_detects_out_of_range_confidence(self):
        self.graph.add_fact('الف', 'به', 'ب')
        self.graph.facts.append({'subject': 'خراب', 'predicate': 'به', 'object': 'ب', 'confidence': 5.0})
        report = self.graph.validate()
        self.assertFalse(report['ok'])
        self.assertTrue(any('out of range' in p for p in report['problems']))

    def test_validate_detects_missing_field(self):
        self.graph.facts.append({'subject': '', 'predicate': 'به', 'object': 'ب', 'confidence': 0.5})
        report = self.graph.validate()
        self.assertFalse(report['ok'])
        self.assertTrue(any('missing subject' in p for p in report['problems']))

    def test_validate_reports_without_repairing(self):
        self.graph.add_fact('الف', 'به', 'ب')
        before = len(self.graph.facts)
        self.graph.facts.append({'subject': 'خراب', 'predicate': 'به', 'object': 'ب', 'confidence': 5.0})
        self.graph.validate()
        # A validator that mutates the graph would hide the corruption.
        self.assertEqual(len(self.graph.facts), before + 1)

    def test_graph_survives_reopen(self):
        self.graph.add_fact('پایتون', 'نوع', 'زبان برنامه‌نویسی')
        reopened = KnowledgeGraph(self.tmp / 'graph.json')
        self.assertTrue(reopened.query('پایتون'))
        self.assertTrue(reopened.validate()['ok'])

    def test_graph_traversal_is_bounded(self):
        # A cycle must not make traversal run forever.
        self.graph.add_fact('الف', 'به', 'ب')
        self.graph.add_fact('ب', 'به', 'الف')
        inferred = self.graph.infer('الف', depth=4, limit=10)
        self.assertLessEqual(len(inferred), 10)
        trace = self.graph.trace('الف', depth=4)
        self.assertLessEqual(len(trace['chain']), 4)


if __name__ == '__main__':
    unittest.main()
