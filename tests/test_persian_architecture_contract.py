from core.dialogue import ConversationState
from core.reference_intelligence import ReferenceIntelligence
from core.reasoning_planning import ReasoningPlanTrace
from memory.store import Memory


def test_persian_reference_memory_and_reasoning_contracts_work_together(tmp_path):
    state = ConversationState(
        current_topic="معماری شناختی ایران",
        topic_stack=["حافظه فارسی", "یادگیری آنلاین"],
    )
    references = ReferenceIntelligence()

    previous = references.resolve("موضوع قبلی", state)
    assert previous.candidate == "یادگیری آنلاین"
    assert previous.ambiguous is False

    continuation = references.resolve("ادامه بده", state)
    assert continuation.candidate == "معماری شناختی ایران"
    assert continuation.ambiguous is False

    # Some persisted/legacy states include the active topic at the end of the stack.
    legacy_state = ConversationState(
        current_topic="یادگیری آنلاین",
        topic_stack=["حافظه فارسی", "یادگیری آنلاین"],
    )
    legacy_previous = references.resolve("موضوع قبلی", legacy_state)
    assert legacy_previous.candidate == "حافظه فارسی"
    assert legacy_previous.ambiguous is False

    legacy_continuation = references.resolve("ادامه بده", legacy_state)
    assert legacy_continuation.candidate == "یادگیری آنلاین"
    assert legacy_continuation.ambiguous is False

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
