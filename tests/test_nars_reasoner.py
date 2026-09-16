import unittest

from core.nars_reasoner import NarsInspiredReasoner, Task


class NarsReasonerTests(unittest.TestCase):
    def test_judgment_and_question(self):
        r = NarsInspiredReasoner()
        r.ingest_task(Task("judgment", "ایران", "پایتخت", "تهران", .95))
        answer = r.ingest_task(Task("question", "ایران", "پایتخت"))
        self.assertEqual(answer.answer, "تهران")
        self.assertGreater(answer.confidence, .8)

    def test_revision_keeps_competing_beliefs(self):
        r = NarsInspiredReasoner()
        r.observe("x", "رنگ", "قرمز", .9, "a")
        r.observe("x", "رنگ", "آبی", .8, "b")
        rows = r.competing("x", "رنگ")
        self.assertEqual(len(rows), 2)
        self.assertEqual(r.best("x", "رنگ").value, "قرمز")

    def test_multihop_derivation(self):
        r = NarsInspiredReasoner()
        r.observe("تهران", "در", "ایران", .9, "seed")
        r.observe("ایران", "قاره", "آسیا", .9, "seed")
        derived = r.derive("تهران", 2)
        values = {(x.subject, x.value) for x in derived}
        self.assertIn(("تهران", "آسیا"), values)


class NarsRuntimeBridgeTests(unittest.TestCase):
    def test_runtime_uses_nars_for_grounded_unknown(self):
        from runtime.app import IranRuntime
        runtime = IranRuntime(".")
        runtime.knowledge.add_fact("رودخانه زاینده رود", "در", "ایران", .95, "test")
        answer = runtime.handle("رودخانه زاینده رود چیست؟")
        runtime.close()
        self.assertEqual(answer, "ایران.")
