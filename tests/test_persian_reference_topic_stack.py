from core.dialogue import ConversationState
from core.reference_intelligence import ReferenceIntelligence


def test_previous_topic_and_continuation_resolve_to_different_stack_entries():
    references = ReferenceIntelligence()

    # Runtime states keep the active topic separate from the prior-topic stack.
    state = ConversationState(
        current_topic="معماری شناختی ایران",
        topic_stack=["حافظه فارسی", "یادگیری آنلاین"],
    )
    previous = references.resolve("موضوع قبلی", state)
    assert previous.candidate == "یادگیری آنلاین"
    assert previous.ambiguous is False

    continuation = references.resolve("ادامه بده", state)
    assert continuation.candidate == "معماری شناختی ایران"
    assert continuation.ambiguous is False

    # Older persisted states may also include the active topic at the stack tail.
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
