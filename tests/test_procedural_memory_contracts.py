"""Procedural memory contracts.

The mission requires procedures to be versioned and testable, and to carry
preconditions, steps, expected result, verification and failure handling.

The store already had the structure and outcome-based confidence updates, and it was
covered indirectly by tests/test_task_c.py. Versioning was the gap: `upsert` overwrote
in place with no version number and no way to see what a procedure looked like before
it changed, so a revision that lowered `success_rate` was unrecoverable.
"""
import tempfile
import unittest
from pathlib import Path

from learning.procedural_memory import ProceduralMemory


class ProceduralMemoryContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.memory = ProceduralMemory(self.tmp / 'procedures.json')

    def test_procedure_stores_full_structure(self):
        row = self.memory.upsert(
            'بررسی سلامت پروژه',
            'اطمینان از سالم بودن پروژه',
            steps=['اجرای تست‌ها', 'بررسی لاگ', 'گزارش نتیجه'],
            preconditions=['true'],
            expected_outcome='همه تست‌ها سبز',
            verification_conditions=['exit_code == 0'],
            failure_conditions=['تست ناموفق'],
        )
        self.assertEqual(row['version'], 1)
        self.assertEqual(row['steps'], ['اجرای تست‌ها', 'بررسی لاگ', 'گزارش نتیجه'])
        self.assertEqual(row['expected_outcome'], 'همه تست‌ها سبز')
        self.assertEqual(row['verification_conditions'], ['exit_code == 0'])
        self.assertEqual(row['failure_conditions'], ['تست ناموفق'])
        self.assertEqual(row['history'], [])

    def test_revision_increments_version(self):
        first = self.memory.upsert('روش الف', 'هدف الف', steps=['قدم ۱'])
        second = self.memory.upsert('روش الف', 'هدف الف', steps=['قدم ۱', 'قدم ۲'])
        self.assertEqual(first['version'], 1)
        self.assertEqual(second['version'], 2)
        self.assertEqual(second['procedure_id'], first['procedure_id'])

    def test_previous_revision_is_recoverable(self):
        first = self.memory.upsert('روش ب', 'هدف ب', steps=['قدم ۱'], success_rate=0.9)
        self.memory.upsert('روش ب', 'هدف ب', steps=['قدم ۱', 'قدم ۲'], success_rate=0.2)
        revision = self.memory.revision_of(first['procedure_id'], version=1)
        self.assertIsNotNone(revision)
        self.assertEqual(revision['steps'], ['قدم ۱'])
        self.assertAlmostEqual(revision['success_rate'], 0.9, places=4)

    def test_versions_lists_history_oldest_first(self):
        created = self.memory.upsert('روش پ', 'هدف پ', steps=['الف'])
        self.memory.upsert('روش پ', 'هدف پ', steps=['الف', 'ب'])
        self.memory.upsert('روش پ', 'هدف پ', steps=['الف', 'ب', 'ج'])
        versions = self.memory.versions(created['procedure_id'])
        self.assertEqual([v['version'] for v in versions], [1, 2, 3])
        self.assertEqual(versions[-1]['steps'], ['الف', 'ب', 'ج'])

    def test_revision_of_unknown_version_returns_none(self):
        created = self.memory.upsert('روش ت', 'هدف ت', steps=['الف'])
        self.assertIsNone(self.memory.revision_of(created['procedure_id'], version=99))

    def test_revision_of_unknown_procedure_returns_none(self):
        self.assertIsNone(self.memory.revision_of('proc_missing'))
        self.assertEqual(self.memory.versions('proc_missing'), [])

    def test_history_is_bounded(self):
        created = self.memory.upsert('روش ث', 'هدف ث', steps=['۰'])
        for index in range(40):
            self.memory.upsert('روش ث', 'هدف ث', steps=[str(index)])
        row = next(p for p in self.memory.procedures if p['procedure_id'] == created['procedure_id'])
        # Unbounded history would grow the store without limit for a hot procedure.
        self.assertLessEqual(len(row['history']), 20)
        self.assertEqual(row['version'], 41)

    def test_record_outcome_updates_rates_without_losing_version(self):
        created = self.memory.upsert('روش ج', 'هدف ج', steps=['الف'])
        updated = self.memory.record_outcome(created['procedure_id'], success=True)
        self.assertEqual(updated['version'], created['version'])
        self.assertGreater(updated['success_rate'], 0.0)
        self.assertGreater(updated['confidence'], created['confidence'])

    def test_preconditions_gate_applicability(self):
        row = self.memory.upsert('روش چ', 'هدف چ', steps=['الف'], preconditions=['evidence'])
        blocked = self.memory.check_preconditions(row, {})
        allowed = self.memory.check_preconditions(row, {'evidence': True})
        self.assertFalse(blocked['applicable'])
        self.assertEqual(blocked['missing'], ['evidence'])
        self.assertTrue(allowed['applicable'])

    def test_retrieve_prefers_matching_goal(self):
        self.memory.upsert('روش ح', 'بررسی حافظه پروژه', steps=['الف'])
        self.memory.upsert('روش خ', 'بررسی شبکه', steps=['ب'])
        results = self.memory.retrieve('بررسی حافظه پروژه')
        self.assertTrue(results)
        self.assertEqual(results[0]['goal'], 'بررسی حافظه پروژه')

    def test_procedures_survive_reopen_with_versions(self):
        created = self.memory.upsert('روش د', 'هدف د', steps=['الف'])
        self.memory.upsert('روش د', 'هدف د', steps=['الف', 'ب'])
        reopened = ProceduralMemory(self.tmp / 'procedures.json')
        versions = reopened.versions(created['procedure_id'])
        self.assertEqual([v['version'] for v in versions], [1, 2])


if __name__ == '__main__':
    unittest.main()
