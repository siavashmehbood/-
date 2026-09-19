import tempfile
import unittest
from pathlib import Path
from learning.input_fabric import InputFabric

class FakeEvents:
    def emit(self, *args, **kwargs):
        pass

class FakeLearning:
    def __init__(self):
        self.calls=[]
    def record(self, **kwargs):
        self.calls.append(kwargs)
        return {"proposal_id": f"test-{len(self.calls)}", "status": "pending"}

class FakeSelfDirected:
    def create_goal(self, *args, **kwargs):
        pass

class FakeRuntime:
    def __init__(self):
        self.events=FakeEvents()
        self.learning=FakeLearning()
        self.self_directed_learning=FakeSelfDirected()

class InputLearningRoutingTests(unittest.TestCase):
    def test_reusable_input_creates_reviewable_learning_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=FakeRuntime()
            fabric=InputFabric(Path(d), runtime=runtime)
            result=fabric.ingest("Python یک زبان برنامه‌نویسی است و برای این آزمون مهم است.", source="user", input_type="knowledge")
            self.assertEqual(len(runtime.learning.calls), 1)
            self.assertEqual(result["learning"][0]["status"], "pending")
            self.assertEqual(runtime.learning.calls[0]["strategy"], "input_fabric")

    def test_questions_and_duplicates_do_not_create_learning_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=FakeRuntime()
            fabric=InputFabric(Path(d), runtime=runtime)
            q=fabric.ingest("چرا این پاسخ درست است؟", source="user", input_type="conversation")
            self.assertEqual(runtime.learning.calls, [])
            self.assertEqual(q["units"][0]["kind"], "question")
            text="این ورودی برای یادگیری تکراری است."
            first=fabric.ingest(text, source="user", input_type="knowledge")
            second=fabric.ingest(text, source="user", input_type="knowledge")
            self.assertFalse(first["duplicate"])
            self.assertTrue(second["duplicate"])
            self.assertEqual(len(runtime.learning.calls), 1)

if __name__=="__main__":
    unittest.main()
