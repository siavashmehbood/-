import unittest
from language_engine.diagnostics import DeploymentMetrics
from evaluation.language.deployment_gate import DeploymentGate
from evaluation.language.transfer_policy import choose_transfer


class DeploymentAndTransferTests(unittest.TestCase):
    def test_resource_gate_is_separate_and_enforced(self):
        m=DeploymentMetrics(tokens_per_second=4,peak_ram_mb=9000,peak_vram_mb=0,cpu_fallback=True)
        result=DeploymentGate(max_ram_mb=8000,min_tokens_per_second=5).evaluate(m)
        self.assertFalse(result["passed"])
        self.assertIn("ram_budget_exceeded",result["reasons"])

    def test_no_transfer_when_foundation_is_within_tolerance(self):
        self.assertEqual(choose_transfer({"delta_to_best":2,"tolerance":3}),"none")

    def test_iran_owned_gap_is_not_model_trained(self):
        self.assertEqual(choose_transfer({"delta_to_best":10,"owner":"memory"}),"fix_iran")

    def test_cross_family_merge_is_not_default(self):
        gap={"delta_to_best":12,"teacher_advantage_repeated":False}
        self.assertEqual(choose_transfer(gap,same_architecture=False),"collect_evidence")


if __name__=="__main__":
    unittest.main()
