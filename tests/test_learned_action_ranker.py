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

    def test_scores_explain_learned_preference_without_executing_it(self):
        ranker = LearnedActionRanker(LearningStub())
        scores = ranker.scores("same goal", ["project_summary", "project_files", "memory_search"])
        self.assertEqual(scores[0]["action"], "project_files")
        self.assertTrue(scores[0]["learned"])
        self.assertEqual(scores[0]["evidence_count"], 2)
        fallback = next(row for row in scores if row["action"] == "memory_search")
        self.assertFalse(fallback["learned"])
        self.assertEqual(fallback["score"], .5)


if __name__ == "__main__":
    unittest.main()
