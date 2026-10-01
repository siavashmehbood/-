import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from integrations.chatgpt_review_worker import ChatGPTReviewWorker
from persistence import StateCorruptionError
from runtime.app import IranRuntime
from security.learning_gate import LearningGate


class ReviewDecisionJournalTests(unittest.TestCase):
    def make_runtime(self, root=None):
        root = root or Path(tempfile.mkdtemp(prefix="iran_journal_"))
        (root / "data").mkdir(exist_ok=True)
        runtime = IranRuntime.__new__(IranRuntime)
        runtime.root = root
        runtime.learning_gate = LearningGate(root / "data" / "learning_proposals.json")
        runtime.chatgpt_review_worker = ChatGPTReviewWorker(root)
        runtime.events = Mock()
        return root, runtime

    @staticmethod
    def add_candidate(runtime, text):
        return runtime.learning_gate.request(
            "learning.record_experience",
            {
                "goal": text,
                "action": "answer",
                "result": "verified",
                "intent": "test",
                "strategy": "unit",
                "domain": "test",
            },
            text,
        )

    def test_journal_hash_chain_is_append_only_and_deduplicated(self):
        root, runtime = self.make_runtime()
        candidate = self.add_candidate(runtime, "audited human rejection")
        runtime.chatgpt_review_worker = ChatGPTReviewWorker(
            root,
            transport=lambda row: {
                "learn": True,
                "reason": "eligible",
                "provider": "test",
                "model": "free-fixture",
            },
        )

        runtime.process_one_chatgpt_learning_review(candidate["proposal_id"])
        runtime.reject_learning(candidate["proposal_id"])
        first = json.loads(
            (root / "data" / "review_decision_journal.json").read_text(encoding="utf-8")
        )
        runtime.sync_chatgpt_learning_reviews()
        runtime.sync_chatgpt_learning_reviews()
        second = json.loads(
            (root / "data" / "review_decision_journal.json").read_text(encoding="utf-8")
        )

        self.assertEqual(first, second)
        self.assertEqual([event["actor"] for event in second], ["reviewer", "human"])
        self.assertEqual([event["decision"] for event in second], ["learn", "rejected"])
        self.assertEqual(second[1]["previous_hash"], second[0]["event_hash"])
        self.assertEqual(runtime.review_decision_journal_status()["count"], 2)
        self.assertEqual(
            runtime.learning_gate.get(candidate["proposal_id"])["status"], "rejected"
        )

    def test_restart_rebuilds_missing_events_and_detects_tampering(self):
        root, runtime = self.make_runtime()
        candidate = self.add_candidate(runtime, "restart journal recovery")
        runtime.chatgpt_review_worker = ChatGPTReviewWorker(
            root, transport=lambda row: {"learn": True, "reason": "eligible"}
        )
        runtime.process_one_chatgpt_learning_review(candidate["proposal_id"])
        runtime.reject_learning(candidate["proposal_id"])

        journal_path = root / "data" / "review_decision_journal.json"
        journal_path.unlink()
        backup_path = journal_path.with_suffix(journal_path.suffix + ".bak")
        if backup_path.exists():
            backup_path.unlink()

        _, restarted = self.make_runtime(root)
        recovered = restarted.sync_chatgpt_learning_reviews()
        self.assertEqual(recovered["reviewed"], 1)
        self.assertEqual(restarted.review_decision_journal_status()["count"], 2)

        events = json.loads(journal_path.read_text(encoding="utf-8"))
        events[0]["decision"] = "reject"
        journal_path.write_text(json.dumps(events), encoding="utf-8")
        with self.assertRaises(StateCorruptionError):
            restarted.review_decision_journal_status()

    def test_health_is_visible_in_learning_status_and_inspect(self):
        root, runtime = self.make_runtime()
        candidate = self.add_candidate(runtime, "visible journal health")
        runtime.chatgpt_review_worker = ChatGPTReviewWorker(
            root, transport=lambda row: {"learn": True, "reason": "eligible"}
        )
        runtime.process_one_chatgpt_learning_review(candidate["proposal_id"])
        runtime.reject_learning(candidate["proposal_id"])
        runtime.effect_learning = Mock()
        runtime.effect_learning.stats.return_value = {}
        runtime.effect_learning.state = {}
        runtime.learning = Mock()
        runtime.learning.learned_lessons = []
        runtime.cognitive_system = Mock()
        runtime.cognitive_system.inspect.return_value = {"version": "test"}

        learning = runtime.learning_status()
        inspected = runtime.inspect()

        self.assertTrue(learning["review_decision_journal"]["valid"])
        self.assertEqual(learning["review_decision_journal"]["count"], 2)
        self.assertEqual(inspected["review_decision_journal"]["count"], 2)

        journal_path = root / "data" / "review_decision_journal.json"
        events = json.loads(journal_path.read_text(encoding="utf-8"))
        events[0]["decision"] = "reject"
        journal_path.write_text(json.dumps(events), encoding="utf-8")

        self.assertFalse(runtime.learning_status()["review_decision_journal"]["valid"])
        self.assertEqual(
            runtime.inspect()["review_decision_journal"]["error"],
            "journal_integrity_error",
        )
        with self.assertRaises(StateCorruptionError):
            runtime.review_decision_journal_status()


if __name__ == "__main__":
    unittest.main()
