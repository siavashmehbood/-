import unittest
from core.learned_action_ranker import LearnedActionRanker


class LearningStub:
    def semantic_lessons(self, goal, limit=100):
        return [
            {"action": "project_summary", "score": .2},
            {"action": "project_summary", "score": .3},
            {"action": "project_files", "score": .9},
            {"action": "project_files", "score": .8},
        ]


class LearnedActionRankerTests(unittest.TestCase):
    def test_successful_action_is_preferred(self):
        ranked = LearnedActionRanker(LearningStub()).rank("same goal", ["project_summary", "project_files"])
        self.assertEqual(ranked[0], "project_files")


if __name__ == "__main__":
    unittest.main()
