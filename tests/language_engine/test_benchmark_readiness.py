import unittest
from pathlib import Path
from evaluation.language.readiness import audit


class BenchmarkReadinessTests(unittest.TestCase):
    def test_repository_protocol_is_ready(self):
        result=audit(Path(__file__).resolve().parents[2])
        self.assertTrue(result.ready,result.reasons)
        self.assertEqual(set(result.candidates),{"qwen35-9b","gemma4-12b"})


if __name__=="__main__":
    unittest.main()
