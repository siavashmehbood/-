from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "core" / "dialogue.refstage.py"
source = MODULE.read_text(encoding="utf-8")
source = source[:source.index("class AnswerPlanner:")] + "\
class ReferenceResolverStage1:" + Path(MODULE).read_text(encoding="utf-8").split("class ReferenceResolverStage1:",1)[1]
ns = {}
exec(compile(source, str(MODULE), "exec"), ns)
ConversationState = ns["ConversationState"]
ReferenceResolver = ns["ReferenceResolverStage1"]


def state_with_topics():
    s = ConversationState()
    for topic in ("پایتون", "Django", "حافظه"):
        s.update(topic, parsed={"goal": topic, "entities": [{"text": topic}]})
    return s


def test_previous_reference_resolves_previous_topic():
    s = state_with_topics()
    s.topic_stack = ["پایتون", "Django"]
    assert ReferenceResolver().resolve("موضوع قبلی", s) == "Django"
    assert ReferenceResolver().resolve("همون قبلی", s) == "Django"


def test_numbered_reference_resolves_topic_position():
    s = state_with_topics()
    s.topic_stack = ["پایتون", "Django"]
    r = ReferenceResolver()
    assert r.resolve("بحث اول", s) == "پایتون"
    assert r.resolve("مورد دوم", s) == "Django"
    assert r.resolve("دومی", s) == "Django"


def test_current_reference_and_followup_use_current_topic():
    s = state_with_topics()
    s.topic_stack = ["پایتون", "Django"]
    r = ReferenceResolver()
    assert r.resolve("همین موضوع", s) == "حافظه"
    assert r.resolve("ادامه بده", s) == "حافظه"
    assert r.resolve("چرا؟", s) == "حافظه"


def test_reference_prefers_structured_current_topic_over_raw_history():
    s = state_with_topics()
    s.topic_stack = ["پایتون", "Django"]
    s.references["latest"] = "Django"
    r = ReferenceResolver()
    assert r.resolve("همونو ادامه بده", s, [("user", "موضوع نامرتبط")]) == "حافظه"
