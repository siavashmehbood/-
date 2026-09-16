"""Memory lifecycle contracts: store, retrieve, update, delete, validate, trace.

The mission requires durable memory to be storable, retrievable, updatable, deletable,
validatable and traceable. Retrieval and storage were already implemented and covered;
update, delete, validate and id tracing were not, and neither was the guard that stops
a destructive delete from wiping everything.

These tests exercise the real SQLite-backed store, not a stub.
"""
import tempfile
import unittest
from pathlib import Path

from memory.store import Memory


class MemoryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.memory = Memory(self.tmp / 'memory.db')

    def tearDown(self):
        self.memory.close()

    # --- store and retrieve -------------------------------------------------

    def test_store_and_retrieve_round_trip(self):
        memory_id = self.memory.add('user', 'پایتون را برای پروژه‌ام می‌خواهم', importance=.7)
        self.assertIsNotNone(memory_id)
        self.assertIn('پایتون', str(self.memory.search('پایتون')))

    def test_repeated_store_does_not_duplicate(self):
        first = self.memory.add('user', 'حافظه پروژه')
        second = self.memory.add('user', 'حافظه پروژه')
        self.assertEqual(first, second)
        self.assertEqual(self.memory.stats()['memories'], 1)

    # --- trace --------------------------------------------------------------

    def test_get_returns_full_row_for_tracing(self):
        memory_id = self.memory.add('user', 'حافظه را بررسی کن', importance=.6, source='test')
        row = self.memory.get(memory_id)
        self.assertEqual(row['id'], memory_id)
        self.assertEqual(row['kind'], 'user')
        self.assertEqual(row['source'], 'test')
        self.assertEqual(row['content'], 'حافظه را بررسی کن')
        for key in ('created_at', 'last_access', 'access_count', 'importance', 'confidence'):
            self.assertIn(key, row)

    def test_get_unknown_id_returns_none(self):
        self.assertIsNone(self.memory.get(999999))

    # --- update -------------------------------------------------------------

    def test_update_changes_only_named_fields(self):
        memory_id = self.memory.add('user', 'متن اصلی', importance=.4, source='original')
        updated = self.memory.update(memory_id, content='متن اصلاح‌شده')
        self.assertEqual(updated['content'], 'متن اصلاح‌شده')
        # Untouched fields must survive an unrelated edit.
        self.assertEqual(updated['source'], 'original')
        self.assertAlmostEqual(updated['importance'], .4, places=5)

    def test_update_clamps_out_of_range_values(self):
        memory_id = self.memory.add('user', 'کران‌ها')
        updated = self.memory.update(memory_id, importance=5.0, confidence=-2.0)
        self.assertEqual(updated['importance'], 1.0)
        self.assertEqual(updated['confidence'], 0.0)

    def test_update_unknown_id_returns_none(self):
        self.assertIsNone(self.memory.update(999999, content='x'))

    def test_update_rejects_empty_content(self):
        memory_id = self.memory.add('user', 'متن معتبر')
        with self.assertRaises(ValueError):
            self.memory.update(memory_id, content='   ')

    # --- delete -------------------------------------------------------------

    def test_forget_by_id_removes_only_that_memory(self):
        keep = self.memory.add('user', 'این باید بماند')
        drop = self.memory.add('user', 'این باید حذف شود')
        result = self.memory.forget(memory_id=drop)
        self.assertEqual(result['deleted'], 1)
        self.assertIsNone(self.memory.get(drop))
        self.assertIsNotNone(self.memory.get(keep))

    def test_forget_by_kind(self):
        self.memory.add('tool_result', 'نتیجه ابزار')
        self.memory.add('user', 'پیام کاربر')
        result = self.memory.forget(kind='tool_result')
        self.assertEqual(result['deleted'], 1)
        self.assertIn('پیام کاربر', str(self.memory.recent(10)))

    def test_forget_without_criteria_is_refused(self):
        # The destructive path must never default to "delete everything".
        self.memory.add('user', 'محافظت‌شده')
        with self.assertRaises(ValueError):
            self.memory.forget()
        self.assertEqual(self.memory.stats()['memories'], 1)

    # --- validate -----------------------------------------------------------

    def test_validate_passes_on_healthy_store(self):
        self.memory.add('user', 'سالم')
        self.memory.add_semantic_fact('پایتون', 'نوع', 'زبان برنامه‌نویسی')
        self.memory.add_lesson('تست', 'همیشه قبل از ادعا شواهد را بررسی کن')
        report = self.memory.validate()
        self.assertTrue(report['ok'], report['problems'])
        self.assertEqual(report['problems'], [])

    def test_validate_detects_corrupted_row(self):
        memory_id = self.memory.add('user', 'رکورد سالم')
        # Simulate corruption that a crash or external writer could produce.
        self.memory.conn.execute(
            'UPDATE memories SET importance=?, confidence=? WHERE id=?', (9.0, -1.0, memory_id)
        )
        self.memory.conn.commit()
        report = self.memory.validate()
        self.assertFalse(report['ok'])
        self.assertTrue(any('out of range' in p for p in report['problems']))

    def test_validate_reports_without_repairing(self):
        memory_id = self.memory.add('user', 'خراب')
        self.memory.conn.execute('UPDATE memories SET importance=? WHERE id=?', (9.0, memory_id))
        self.memory.conn.commit()
        self.memory.validate()
        # A validator that silently repairs would hide the corruption.
        row = self.memory.get(memory_id)
        self.assertEqual(row['importance'], 9.0)

    # --- persistence --------------------------------------------------------

    def test_lifecycle_survives_reopen(self):
        memory_id = self.memory.add('user', 'پایدار')
        self.memory.update(memory_id, importance=.9)
        self.memory.close()

        reopened = Memory(self.tmp / 'memory.db')
        try:
            row = reopened.get(memory_id)
            self.assertIsNotNone(row)
            self.assertAlmostEqual(row['importance'], .9, places=5)
            self.assertTrue(reopened.validate()['ok'])
        finally:
            reopened.close()


if __name__ == '__main__':
    unittest.main()
