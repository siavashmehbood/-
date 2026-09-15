import unittest

from core.virtual_world import VirtualWorld, VirtualWorldBenchmark


class VirtualWorldTests(unittest.TestCase):
    def test_world_requires_observation_before_safe_action(self):
        world = VirtualWorld()
        world.state["system"] = "degraded"
        self.assertIn("restore", world.legal_actions())
        result = world.act("restore")
        self.assertTrue(result["success"])
        self.assertEqual(result["after"]["system"], "healthy")

    def test_benchmark_reaches_goal_without_external_answer(self):
        result = VirtualWorldBenchmark().run(cycles=50)
        self.assertTrue(result["success"])
        self.assertLessEqual(result["cycles"], 50)
        self.assertGreaterEqual(len(result["history"]), 1)


if __name__ == "__main__":
    unittest.main()
