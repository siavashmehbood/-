import unittest
from learning.trusted_knowledge import TrustedKnowledgeBootstrap


class TrustedKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.engine = TrustedKnowledgeBootstrap()

    def test_rejects_unrelated_or_non_independent_sources(self):
        result = self.engine.build("X social network history", [
            {"source_id":"wiki-x", "url":"https://en.wikipedia.org/wiki/X_(social_network)", "title":"X (social network)", "text":"X is a social networking service. It was launched in 2006 and was known as Twitter until 2023.", "confidence":.82},
            {"source_id":"wiki-virus", "url":"https://en.wikipedia.org/wiki/Computer_virus", "title":"Computer virus history", "text":"Elk Cloner appeared on the Apple II and is described as an early computer virus. The term computer virus was later used by Frederick Cohen.", "confidence":.82},
        ])
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("sources_not_independent", result["issues"])
        self.assertIn("weak_source_relevance", result["issues"])
        self.assertEqual(result["agreements"], [])

    def test_builds_reviewable_proposal_only_from_independent_agreement(self):
        result = self.engine.build("X social network", [
            {"source_id":"a", "url":"https://example.org/x", "title":"X social network", "text":"X is a social networking service. It was launched in 2006 and was formerly known as Twitter.", "confidence":.9},
            {"source_id":"b", "url":"https://example.net/x", "title":"X social network history", "text":"X is a social networking service. The service launched in 2006 and was formerly known as Twitter.", "confidence":.9},
        ])
        self.assertEqual(result["status"], "ready_for_review")
        self.assertGreaterEqual(result["independent_source_count"], 2)
        self.assertTrue(result["agreements"])
        self.assertGreater(result["confidence"], .5)
        self.assertTrue(all(s["text"] for s in result["sources"]))

    def test_broken_extraction_is_never_an_agreement(self):
        result = self.engine.build("X social network", [
            {"source_id":"a", "url":"https://a.example/x", "title":"X social network", "text":"X is a social networking service. history, edit, and", "confidence":.9},
            {"source_id":"b", "url":"https://b.example/x", "title":"X social network", "text":"X is a social networking service. history, edit, and", "confidence":.9},
        ])
        self.assertEqual(result["agreements"], [])
        self.assertIn("no_cross_source_agreement", result["issues"])


if __name__ == "__main__":
    unittest.main()
