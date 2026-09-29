"""Persian E2E: A1 (reference/current_topic) + A3 (memory semantic + persistence)."""
import tempfile, os
from core.dialogue import ConversationState
from core.reference_intelligence import ReferenceIntelligence
from core.reasoning_planning import ReasoningPlanTrace
from memory.store import Memory

def test_e2e():
    with tempfile.TemporaryDirectory() as d:
        # Memory (A3)
        mem = Memory(os.path.join(d, "mem.db"))
        mem.add_semantic_fact("معماری شناختی ایران", "نوع", "موضوع")
        # Dialogue state (topic stack + current_topic + persistence)
        state = ConversationState()
        state.current_topic = "معماری شناختی ایران"
        state.topic_stack = ["حافظه فارسی", "یادگیری"]
        state.active_goal = "ادامه بحث"
        state.unresolved_questions = ["چرا؟"]
        state.corrections = ["اشتباهه"]
        # Reference (A1) — must preserve current_topic for previous trigger
        res = ReferenceIntelligence().resolve("همون قبلی رو ادامه بده", state)
        # Memory retrieval — semantic search with persian ZWNJ normal
        sem = mem.semantic_search("معماری شناختی")
        # Persistence — save/load preserves normalization
        path = os.path.join(d, "state.json")
        state.save(path)
        state2 = ConversationState.load(path)
        # Assertions (verifiable)
        assert res.candidate == "معماری شناختی ایران", f"A1 ref FAIL: {res.candidate}"
        assert len(sem) >= 1, f"A3 semantic FAIL: {len(sem)}"
        assert all("\u200c" not in str(x) for x in state2.corrections), "norm FAIL"
        assert state2.current_topic == state.current_topic, "persistence FAIL"
