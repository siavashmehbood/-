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

    def test_every_scenario_turns_field_is_a_tuple_of_turns(self):
        for scenario in PersianConversationBenchmark().scenarios():
            self.assertIsInstance(
                scenario.turns, tuple,
                f'{scenario.name}: turns must be a tuple, a bare string is iterated char-by-char',
            )
            self.assertTrue(all(isinstance(turn, str) for turn in scenario.turns))

    def test_scenarios_run_against_an_isolated_runtime(self):
        from benchmarks.runtime_factory import isolated_runtime_factory

        report = PersianConversationBenchmark().run(isolated_runtime_factory())
        self.assertEqual(report['total'], 100)
        self.assertEqual(len(report['results']), 100)


if __name__ == '__main__':
    unittest.main()
