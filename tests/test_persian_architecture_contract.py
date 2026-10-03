from core.dialogue import ConversationState
from core.reference_intelligence import ReferenceIntelligence
from core.reasoning_planning import ReasoningPlanTrace
from memory.store import Memory


def test_persian_reference_memory_and_reasoning_contracts_work_together(tmp_path):
    state = ConversationState(
        current_topic="معماری شناختی ایران",
        topic_stack=["حافظه فارسی", "یادگیری آنلاین"],
    )
    resolution = ReferenceIntelligence().resolve("موضوع قبلی", state)
    assert resolution.candidate == "یادگیری آنلاین"

    with Memory(tmp_path / "memory.sqlite") as memory:
        memory.add_semantic_fact(
            "معماری شناختی ایران",
            "نوع",
            "موضوع",
            source="explicit",
        )
        assert memory.semantic_search("معماری شناختی ایران")

    trace = ReasoningPlanTrace(
        goal="بررسی سازگاری معماری",
        intent="analysis",
        contradictions=["تعارض در شواهد"],
    )
    assert trace.verifier_state == "REPAIR"
