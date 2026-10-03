"""Architecture regression for the canonical CognitivePipeline entrypoint."""
import inspect
from pathlib import Path

from core.cognitive_pipeline import CognitivePipeline


def test_cognitive_pipeline_has_one_canonical_run_owner():
    source=Path("core/cognitive_pipeline.py").read_text(encoding="utf-8")
    assert source.count("    def run(self, text):") == 1
    assert CognitivePipeline.run.__qualname__ == "CognitivePipeline.run"
    assert inspect.isfunction(CognitivePipeline.run)

    forbidden=(
        "_pipeline_run_legacy",
        "_pipeline_run_v41c",
        "_pipeline_v55_base",
        "_pipeline_v56_base",
        "_pipeline_v57_base",
        "_pipeline_v58_base",
        "_pipeline_v59_base",
        "_pipeline_v60_base",
        "_pipeline_v61_base",
        "_pipeline_v62_base",
        "_pipeline_v63_base",
        "_pipeline_self_correction_base",
        "_pipeline_v65_base",
        "_pipeline_v66_base",
    )
    assert not any(name in source for name in forbidden)


def test_canonical_pipeline_is_not_monkeypatched_at_module_scope():
    source=Path("core/cognitive_pipeline.py").read_text(encoding="utf-8")
    assert "CognitivePipeline.run =" not in source
    assert "setattr(CognitivePipeline" not in source


def test_dialogue_has_one_canonical_handle_binding():
    import re
    from types import SimpleNamespace
    from core.dialogue import LocalDialogueEngine

    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    bindings=re.findall(r"(?m)^LocalDialogueEngine\.handle\s*=\s*([A-Za-z0-9_]+)",source)
    assert bindings == ["_canonical_pipeline_handle"]

    calls=[]
    class Canonical:
        def dispatch(self,text):
            calls.append(text)
            return "canonical-response"

    dialogue=SimpleNamespace(_canonical_system=Canonical())
    assert LocalDialogueEngine.handle(dialogue,"ادامه بده") == "canonical-response"
    assert calls == ["ادامه بده"]


def test_conversation_state_update_is_class_owned_and_preserves_semantics():
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    assert "ConversationState.update =" not in source
    assert "ConversationState.update=" not in source

    from core.dialogue import ConversationState
    assert ConversationState.update.__qualname__ == "ConversationState.update"
    state=ConversationState(current_topic="پایتون")

    state.update("سلام", parsed={"intent":"social"})
    assert state.current_topic == "پایتون"

    state.update("منظورم حافظه بود", parsed={"intent":"correction"}, confidence=.8)
    assert state.current_topic == "حافظه"
    assert state.references["latest"] == "حافظه"

    state.update(
        "این قسمت را بهتر کن",
        parsed={"intent":"command", "question_units":["این قسمت را بهتر کن"]},
        confidence=.9,
        reference="Django",
    )
    assert state.current_topic == "Django"
    assert state.references["latest_topic"] == "Django"
    assert state.turns == 3


def test_dialogue_cleanup_preserves_required_runtime_hooks():
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    # State and memory hooks still affect the canonical pipeline. Reference
    # resolution is now class-owned and must not be rebound at module scope.
    assert "LocalDialogueEngine.__init__ = _chain_init" in source
    assert "LocalDialogueEngine._memory = _memory_chain_context" in source
    assert "ReferenceResolver.resolve =" not in source
    assert "ReferenceResolver=ReferenceResolverStage1" not in source
    assert "LocalDialogueEngine.handle = _canonical_pipeline_handle" in source


def test_question_analyzer_and_answer_verifier_are_class_owned():
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    assert "QuestionAnalyzer.analyze =" not in source
    assert "AnswerVerifier.verify =" not in source
    assert "def _analyze_v2(" not in source
    assert "def _analyze_v3(" not in source
    assert "def _analyze_v4(" not in source
    assert "def _verify_v2(" not in source

    from core.dialogue import QuestionAnalyzer, AnswerVerifier, CognitiveContext, AnswerPlan
    parsed=QuestionAnalyzer().analyze("پایتون چیه و چرا محبوب است؟")
    assert parsed["question_type"] == "why"
    assert parsed["question_units"] == ["پایتون چیه", "چرا محبوب است"]

    context=CognitiveContext(
        user_message="چرا؟",
        question_type="why",
        question_units=["چرا؟"],
        uncertainty=.9,
    )
    plan=AnswerPlan(["چرا؟"], answer_type="UNKNOWN")
    result=AnswerVerifier().verify(
        context,
        "اطلاعات کافی ندارم؛ نمی‌خواهم حدس بزنم.",
        plan,
    )
    assert result.status == "PASS"


def test_reference_resolver_is_class_owned_and_uses_reference_intelligence():
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    assert "ReferenceResolver.resolve =" not in source
    assert "ReferenceResolver=ReferenceResolverStage1" not in source
    assert "def _reference_resolve_v2(" not in source
    assert "def _resolve_chain_context(" not in source

    from core.dialogue import ConversationState, ReferenceResolver, ReferenceResolverStage1
    assert ReferenceResolver is not ReferenceResolverStage1

    state=ConversationState()
    state.topic_stack=["پایتون","Django"]
    state.current_topic="حافظه"
    state.active_goal="حافظه"
    resolver=ReferenceResolver()

    assert resolver.resolve("موضوع قبلی",state) == "Django"
    assert resolver.resolve("بحث اول",state) == "پایتون"
    assert resolver.resolve("همین موضوع",state) == "حافظه"
    assert "reference_trace" in state.references
    assert isinstance(state.references["reference_trace"],dict)

def test_direct_answer_is_class_owned_and_preserves_priority_contracts():
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    assert "LocalDialogueEngine._direct_answer =" not in source
    assert "LocalDialogueEngine._direct_answer=" not in source
    assert "def _direct_answer_v" not in source

    from types import SimpleNamespace
    from core.dialogue import CognitiveContext, LocalDialogueEngine

    assert LocalDialogueEngine._direct_answer.__qualname__ == (
        "LocalDialogueEngine._direct_answer"
    )

    dialogue=SimpleNamespace()
    feedback=CognitiveContext(user_message="درست بود")
    assert LocalDialogueEngine._direct_answer(dialogue,feedback) == (
        "بازخورد شما ثبت شد و برای انتخاب راهبرد پاسخ‌های بعدی استفاده می‌شود."
    )

    compound=CognitiveContext(
        user_message="پایتون چیه و چرا محبوب است؟",
        question_type="why",
        question_units=["پایتون چیه","چرا محبوب است"],
    )
    answer=LocalDialogueEngine._direct_answer(dialogue,compound)
    assert answer.splitlines() == [
        "1) پایتون یک زبان برنامه‌نویسی سطح‌بالا و چندمنظوره است.",
        "2) به‌خاطر خوانایی، کتابخانه‌های گسترده و کاربردهای متنوع محبوب است.",
    ]

def test_dialogue_knowledge_is_class_owned_and_preserves_local_facts():
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    assert "LocalDialogueEngine._knowledge =" not in source
    assert "LocalDialogueEngine._knowledge=" not in source
    assert "def _knowledge_v" not in source

    from types import SimpleNamespace
    from core.dialogue import LocalDialogueEngine

    assert LocalDialogueEngine._knowledge.__qualname__ == (
        "LocalDialogueEngine._knowledge"
    )
    dialogue=SimpleNamespace(runtime=SimpleNamespace(knowledge=None))

    political=LocalDialogueEngine._knowledge(
        dialogue,
        "مرکز سیاسی کشور ایران چیست؟",
        {},
    )
    assert political == [{
        "subject": "ایران",
        "predicate": "پایتخت",
        "object": "تهران",
        "confidence": .99,
        "source": "verified_local_seed",
    }]

    week=LocalDialogueEngine._knowledge(dialogue,"هفته چند روز دارد؟",{})
    assert week == [{
        "subject": "هفته",
        "predicate": "تعداد روز",
        "object": "هفت",
        "confidence": .99,
        "source": "verified_local_seed",
    }]

