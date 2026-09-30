from core.dialogue import ConversationState, QuestionAnalyzer, ReferenceResolverStage1


def state_with_topics():
    s = ConversationState()
    s.topic_stack = ["پایتون", "Django"]
    s.current_topic = "حافظه"
    s.active_goal = "حافظه"
    return s


def test_previous_reference_resolves_previous_topic():
    s = state_with_topics()
    r = ReferenceResolverStage1()
    assert r.resolve("موضوع قبلی", s) == "Django"
    assert r.resolve("همون قبلی", s) == "Django"


def test_numbered_reference_resolves_topic_position():
    s = state_with_topics()
    r = ReferenceResolverStage1()
    assert r.resolve("بحث اول", s) == "پایتون"
    assert r.resolve("مورد دوم", s) == "Django"
    assert r.resolve("دومی", s) == "Django"


def test_current_reference_and_followup_use_current_topic():
    s = state_with_topics()
    r = ReferenceResolverStage1()
    assert r.resolve("همین موضوع", s) == "حافظه"
    assert r.resolve("ادامه بده", s) == "حافظه"
    assert r.resolve("چرا؟", s) == "حافظه"


def test_reference_prefers_structured_current_topic():
    s = state_with_topics()
    s.references["latest"] = "Django"
    r = ReferenceResolverStage1()
    assert r.resolve("همونو ادامه بده", s, [("user", "موضوع نامرتبط")]) == "حافظه"

def test_legacy_stack_tail_does_not_return_current_topic_as_previous():
    s = ConversationState(
        current_topic="Django",
        topic_stack=["پایتون", "Django"],
        active_goal="Django",
    )
    r = ReferenceResolverStage1()

    assert r.resolve("موضوع قبلی", s) == "پایتون"
    assert r.resolve("همون قبلی", s) == "پایتون"
    assert r.resolve("ادامه بده", s) == "Django"

def test_numbered_reference_matches_canonical_ordinals_through_fifth():
    s = ConversationState(
        current_topic="معماری",
        topic_stack=["پایتون", "Django", "حافظه", "یادگیری"],
        active_goal="معماری",
    )
    r = ReferenceResolverStage1()

    assert r.resolve("موضوع سوم", s) == "حافظه"
    assert r.resolve("چهارمیش", s) == "یادگیری"
    assert r.resolve("بحث پنجم", s) == "معماری"

def test_question_analyzer_treats_all_ordinal_topics_as_followups():
    analyzer = QuestionAnalyzer()

    for text in ("اولین مورد", "موضوع سوم", "بحث چهارم", "مورد پنجم"):
        assert analyzer.analyze(text)["question_type"] == "follow_up"


def test_legacy_stack_tail_is_not_counted_twice_for_ordinals():
    s = ConversationState(
        current_topic="حافظه",
        topic_stack=["پایتون", "Django", "حافظه"],
        active_goal="حافظه",
    )
    r = ReferenceResolverStage1()

    assert s.topic_by_index(3) == "حافظه"
    assert s.topic_by_index(4) == ""
    assert r.resolve("موضوع سوم", s) == "حافظه"
    assert r.resolve("موضوع چهارم", s) == ""
