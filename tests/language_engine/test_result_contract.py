import unittest
from evaluation.language.result_contract import validate_result,validate_pair


def row(round_="quality_baseline"):
    return {
      "candidate_id":"x","model_id":"org/x","revision":"abc","round":round_,
      "gate_metrics":{"persian":90,"multilingual_average":80,"language_minimum":70,
        "multilingual_loss":1,"critical_language_loss":1,"capability_loss":1,
        "iran_regressions":0,"one_brain":True,"offline":True,"hidden_gate":True},
      "quality_metrics":{"persian":90,"multilingual":80,"reasoning_knowledge":80,
        "context_instruction":80,"code":80,"tool_agent":80,"safety":80},
      "deployment":{"first_token_ms":100,"total_latency_ms":1000,"tokens_per_second":20,
        "peak_ram_mb":6000,"context_tokens":4096,"cpu_fallback":False},
      "provenance":{"runtime":"local","hardware":"test","quantization":"q4",
        "timestamp":"2026-01-01T00:00:00Z","dataset_fingerprint":"sha256:test"}}


class ResultContractTests(unittest.TestCase):
    def test_complete_result(self): self.assertTrue(validate_result(row()))
    def test_missing_provenance_fails(self):
        x=row(); del x["provenance"]["hardware"]
        with self.assertRaises(ValueError): validate_result(x)
    def test_two_rounds_required(self):
        with self.assertRaises(ValueError): validate_pair([row()])
        self.assertTrue(validate_pair([row(),row("deployment")]))


if __name__=="__main__": unittest.main()
