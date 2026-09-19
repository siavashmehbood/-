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
    def __init__(self):
        self.calls=[]
    def create_goal(self, *args, **kwargs):
        self.calls.append((args, kwargs))

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

    def test_input_classification_is_single_purpose(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=FakeRuntime(); fabric=InputFabric(Path(d), runtime=runtime)
            q=fabric.ingest("چرا این پاسخ درست است؟", source="user", input_type="conversation")
            self.assertEqual([u["kind"] for u in q["units"]], ["question"])
            c=fabric.ingest("اشتباه است، این بخش را اصلاح کن", source="user", input_type="conversation")
            self.assertEqual([u["kind"] for u in c["units"]], ["correction"])
            code=fabric.ingest("def hello(): return 1", source="user", input_type="code")
            self.assertEqual([u["kind"] for u in code["units"]], ["procedure_candidate"])

    def test_normal_conversation_does_not_become_learning_goal(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=FakeRuntime(); fabric=InputFabric(Path(d), runtime=runtime)
            result=fabric.ingest("من امروز درباره پایتون صحبت می‌کنم.", source="user", input_type="conversation")
            self.assertEqual(runtime.learning.calls, [])
            self.assertEqual(runtime.self_directed_learning.calls, [])
            self.assertEqual(result["units"][0]["kind"], "observation")

    def test_questions_and_duplicates_do_not_create_learning_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=FakeRuntime(); fabric=InputFabric(Path(d), runtime=runtime)
            q=fabric.ingest("چرا این پاسخ درست است؟", source="user", input_type="conversation")
            self.assertEqual(runtime.learning.calls, [])
            text="این ورودی برای یادگیری تکراری است."
            first=fabric.ingest(text, source="user", input_type="knowledge")
            second=fabric.ingest(text, source="user", input_type="knowledge")
            self.assertFalse(first["duplicate"]); self.assertTrue(second["duplicate"])
            self.assertEqual(len(runtime.learning.calls), 1)
            self.assertEqual(len(runtime.self_directed_learning.calls), 0)

    def test_learning_errors_are_visible(self):
        with tempfile.TemporaryDirectory() as d:
            runtime=FakeRuntime()
            runtime.learning.record=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("x"))
            fabric=InputFabric(Path(d), runtime=runtime)
            result=fabric.ingest("Python یک زبان برنامه‌نویسی است.", source="user", input_type="knowledge")
            self.assertEqual(len(result["learning" ]), 0)
            self.assertEqual(result["learning_errors"][0]["error"], "RuntimeError")

if __name__=="__main__":
    unittest.main()
