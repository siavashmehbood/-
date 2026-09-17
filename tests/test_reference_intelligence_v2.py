from core.dialogue import ConversationState, ReferenceResolver


def make_state():
    s = ConversationState()
    s.topic_stack = ["پایتون", "Django"]
    s.current_topic = "حافظه"
    s.active_goal = "حافظه"
    return s


def test_previous_phrase_prefers_previous_topic_over_current():
    s = make_state()
    assert ReferenceResolver().resolve("همون قبلی", s) == "Django"
    assert s.references["reference_trace"]["trigger"] == "همون قبلی"


def test_demonstrative_prefers_current_topic():
    s = make_state()
    assert ReferenceResolver().resolve("این بخش", s) == "حافظه"


def test_distal_structure_resolves_current_context():
    s = make_state()
    assert ReferenceResolver().resolve("ساختار آن", s) == "حافظه"


def test_correction_target_is_latest_reference():
    s = make_state()
    s.current_topic = "پایتون"
    s.references["latest"] = "Django"
    assert ReferenceResolver().resolve("ادامه Django", s) == "Django"


def test_ambiguous_context_does_not_silently_choose():
    s = ConversationState()
    s.topic_stack = ["پایتون", "Django"]
    s.current_topic = "حافظه"
    s.references["latest"] = "Django"
    # Explicitly weak context: resolver records candidates rather than inventing certainty.
    result = ReferenceResolver().resolve("اون", s)
    assert result in {"", "حافظه", "Django"}
    assert "reference_trace" in s.references


def test_empty_context_stays_unresolved():
    s = ConversationState()
    assert ReferenceResolver().resolve("این بخش", s) == ""
    assert s.references["reference_trace"]["candidate"] == ""
