from core.dialogue import ConversationState, ReferenceResolverStage1


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