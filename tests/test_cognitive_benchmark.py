import unittest

from benchmarks.cognitive_benchmark import CognitiveBenchmark


class CognitiveBenchmarkTests(unittest.TestCase):
    def test_has_100_cases_and_ten_categories(self):
        benchmark = CognitiveBenchmark()
        self.assertEqual(len(benchmark.cases), 100)
        self.assertEqual({c.category for c in benchmark.cases}, set(benchmark.CATEGORIES))
        self.assertEqual([sum(c.category == x for c in benchmark.cases) for x in benchmark.CATEGORIES], [10] * 10)

    def test_benchmark_contract(self):
        report = CognitiveBenchmark().run()
        self.assertEqual(report["total"], 100)
        self.assertEqual(report["passed"] + report["failed"], 100)
        self.assertEqual(set(report["categories"]), set(CognitiveBenchmark.CATEGORIES))


if __name__ == "__main__":
    unittest.main()
