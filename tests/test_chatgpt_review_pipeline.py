import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from integrations.chatgpt_review_worker import ChatGPTReviewWorker, RateLimitError
from runtime.app import IranRuntime
from security.learning_gate import LearningGate


class ChatGPTReviewPipelineTests(unittest.TestCase):
    def make_runtime(self):
        root = Path(tempfile.mkdtemp(prefix="iran_review_"))
        (root / "data").mkdir()
        gate = LearningGate(root / "data" / "learning_proposals.json")
        runtime = IranRuntime.__new__(IranRuntime)
        runtime.root = root
        runtime.learning_gate = gate
        runtime.chatgpt_review_worker = ChatGPTReviewWorker(root)
        runtime.events = Mock()
        return root, runtime, gate

    def add_candidate(self, gate, text="candidate"):
        return gate.request("learning.record_experience", {
            "goal": text, "action": "answer", "result": "verified", "intent": "test",
            "strategy": "unit", "domain": "test",
        }, text)

    def test_candidate_starts_pending_and_readers_do_not_call_api(self):
        root, runtime, gate = self.make_runtime()
        candidate = self.add_candidate(gate)
        runtime.sync_chatgpt_learning_reviews()
        self.assertEqual(candidate["status"], "pending")
        row = json.loads((root / "data" / "chatgpt_reviews.json").read_text())
        self.assertEqual(row[0]["review_status"], "not_reviewed")
        runtime.sync_chatgpt_learning_reviews = Mock(side_effect=AssertionError("read path called sync"))
        self.assertEqual(runtime.learning_pending(10)[0]["proposal_id"], candidate["proposal_id"])
        self.assertEqual(runtime.chatgpt_learning_review_status(candidate["proposal_id"])["reviewed"], False)

    def test_learn_true_routes_to_human_pending(self):
        root, runtime, gate = self.make_runtime()
        candidate = self.add_candidate(gate)
        worker = ChatGPTReviewWorker(root, transport=lambda row: {"learn": True, "reason": "sound", "confidence": 0.9})
        runtime.chatgpt_review_worker = worker
        result = runtime.process_one_chatgpt_learning_review()
        self.assertTrue(result["ok"])
        review = runtime.chatgpt_learning_review_status(candidate["proposal_id"])["row"]
        self.assertEqual(review["status"], "human_pending")
        self.assertEqual(review["chatgpt_decision"], "learn")
        self.assertEqual(runtime.human_learning_pending(10)[0]["proposal_id"], candidate["proposal_id"])

    def test_learn_false_rejects_without_human_queue(self):
        root, runtime, gate = self.make_runtime()
        candidate = self.add_candidate(gate)
        runtime.chatgpt_review_worker = ChatGPTReviewWorker(root, transport=lambda row: {"learn": False, "reason": "insufficient"})
        result = runtime.process_one_chatgpt_learning_review()
        self.assertTrue(result["ok"])
        self.assertEqual(gate.get(candidate["proposal_id"])["status"], "rejected")
        review = runtime.chatgpt_learning_review_status(candidate["proposal_id"])["row"]
        self.assertEqual(review["status"], "rejected")
        self.assertEqual(runtime.human_learning_pending(10), [])

    def test_human_reject_updates_review_without_learning(self):
        root, runtime, gate = self.make_runtime()
        candidate = self.add_candidate(gate, "human decision")
        runtime.chatgpt_review_worker = ChatGPTReviewWorker(root, transport=lambda row: {"learn": True, "reason": "eligible"})
        runtime.process_one_chatgpt_learning_review()
        result = runtime.reject_learning(candidate["proposal_id"])
        self.assertTrue(result["ok"])
        self.assertEqual(gate.get(candidate["proposal_id"])["status"], "rejected")
        review = runtime.chatgpt_learning_review_status(candidate["proposal_id"])["row"]
        self.assertEqual(review["human_decision"], "rejected")
        self.assertEqual(review["status"], "rejected")

    def test_429_preserves_candidate_and_cooldown_blocks_spam(self):
        root, runtime, gate = self.make_runtime()
        candidate = self.add_candidate(gate)
        calls = []

        def limited(row):
            calls.append(row["proposal_id"])
            raise RateLimitError()

        worker = ChatGPTReviewWorker(root, transport=limited)
        runtime.chatgpt_review_worker = worker
        first = runtime.process_one_chatgpt_learning_review()
        second = runtime.process_one_chatgpt_learning_review()
        self.assertEqual(first["reason"], "rate_limited")
        self.assertEqual(second["reason"], "cooldown")
        self.assertEqual(len(calls), 1)
        self.assertEqual(gate.get(candidate["proposal_id"])["status"], "pending")
        state = json.loads((root / "data" / "chatgpt_review_state.json").read_text())
        self.assertEqual(state["last_error"], "HTTP 429")
        self.assertIsNotNone(state["next_allowed_at"])

    def test_duplicate_candidates_and_restart_preserve_state(self):
        root, runtime, gate = self.make_runtime()
        first = self.add_candidate(gate, "same")
        second = self.add_candidate(gate, "same")
        self.assertEqual(first["proposal_id"], second["proposal_id"])
        runtime.sync_chatgpt_learning_reviews()
        rows = json.loads((root / "data" / "chatgpt_reviews.json").read_text())
        self.assertEqual(len(rows), 1)
        worker = ChatGPTReviewWorker(root, transport=lambda row: {"learn": True, "reason": "ok"})
        worker.process_one()
        restarted = ChatGPTReviewWorker(root, transport=unittest.mock.Mock())
        self.assertEqual(restarted.status()["last_success_at"] is not None, True)
        self.assertEqual(restarted.status()["cooldown"], True)
        restarted.transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
