"""Cross-module: reference + memory + planning + verifier."""
from core.dialogue import ConversationState
from core.reference_intelligence import ReferenceIntelligence
from core.reasoning_planning import ReasoningPlanTrace
from memory.store import Memory

def test_cross_module():
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        mem = Memory(os.path.join(d,"db"))
        mem.add_semantic_fact("معماری شناختی ایران","نوع","موضوع")
        s = ConversationState(); s.current_topic = "معماری شناختی ایران"; s.topic_stack = ["حافظه فارسی"]
        res = ReferenceIntelligence().resolve("همون قبلی رو ادامه بده", s)
        trace = ReasoningPlanTrace(goal="بهبود حافظه", intent="plan", contradictions=["تعارض"])
        assert res.candidate == "معماری شناختی ایران"
        assert len(mem.semantic_search("معماری")) >= 1
        assert hasattr(trace, "verifier_state")
        mem.close()
