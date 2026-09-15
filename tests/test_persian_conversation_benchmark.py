import unittest
from benchmarks.persian_conversation_benchmark import PersianConversationBenchmark


class PersianConversationBenchmarkTests(unittest.TestCase):
    def test_has_100_deterministic_scenarios(self):
        benchmark = PersianConversationBenchmark()
        first = benchmark.scenarios()
        second = benchmark.scenarios()
        self.assertEqual(len(first), 100)
        self.assertEqual(first, second)
        self.assertTrue(all(s.turns and s.checks for s in first))


if __name__ == '__main__': unittest.main()
