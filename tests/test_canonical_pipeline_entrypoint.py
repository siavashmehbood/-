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


def test_dialogue_handle_is_class_owned_and_delegates_to_canonical_brain():
    from types import SimpleNamespace
    from core.dialogue import LocalDialogueEngine

    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    assert "LocalDialogueEngine.handle =" not in source
    assert "_canonical_pipeline_handle" not in source
    assert LocalDialogueEngine.handle.__qualname__ == "LocalDialogueEngine.handle"

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


def test_dialogue_cleanup_preserves_required_runtime_hooks_as_class_owned_methods():
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    from core.dialogue import LocalDialogueEngine

    assert "LocalDialogueEngine.__init__ =" not in source
    assert "LocalDialogueEngine._memory =" not in source
    assert "LocalDialogueEngine.handle =" not in source
    assert "_chain_init" not in source
    assert "_memory_chain_context" not in source
    assert "ReferenceResolver.resolve =" not in source
    assert "ReferenceResolverStage1" not in source

    init_src=inspect.getsource(LocalDialogueEngine.__init__)
    memory_src=inspect.getsource(LocalDialogueEngine._memory)
    handle_src=inspect.getsource(LocalDialogueEngine.handle)
    assert "ChainReasoner" in init_src
    assert "working_context" in memory_src
    assert "_canonical_system" in handle_src


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


def test_answer_repair_is_class_owned_and_preserves_learning_policy():
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    assert "AnswerRepair.repair =" not in source
    assert "_repair_learning" not in source
    assert "_PREV_REPAIR_LEARNING" not in source

    from core.dialogue import AnswerRepair, CognitiveContext, AnswerPlan, Verification
    assert AnswerRepair.repair.__qualname__ == "AnswerRepair.repair"
    repair=AnswerRepair()

    uncertain=CognitiveContext(
        user_message="ادامه بده",
        uncertainty=.9,
        relevant_knowledge=[],
    )
    plan=AnswerPlan(["ادامه بده"],steps=["avoid_recent_failed_pattern"])
    verification=Verification("PASS",score=.9)
    guarded=repair.repair(uncertain,"پاسخ قبلی",verification,plan)
    assert guarded.startswith("UNKNOWN:")

    follow=CognitiveContext(
        user_message="چرا؟",
        question_type="follow_up",
        current_topic="پایتون",
    )
    follow_plan=AnswerPlan(["چرا؟"],steps=["preserve_conversation_context"])
    followed=repair.repair(follow,"چون خواناست.",verification,follow_plan)
    assert "پایتون" in followed
    assert "چون خواناست" in followed


def test_dialogue_module_has_no_live_class_method_monkeypatches():
    import re
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    bindings=re.findall(
        r"(?m)^[A-Z][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\s*=\s*[A-Za-z_]",
        source,
    )
    assert bindings == []


def test_reference_resolver_is_class_owned_and_uses_reference_intelligence():
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    assert "ReferenceResolver.resolve =" not in source
    assert "ReferenceResolverStage1" not in source
    assert "def _reference_resolve_v2(" not in source
    assert "def _resolve_chain_context(" not in source

    from core.dialogue import ConversationState, ReferenceResolver
    assert ReferenceResolver.__qualname__ == "ReferenceResolver"

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

def test_reference_markers_are_static_and_preserve_resolution():
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    assert source.count("REF_MARKERS = (") == 1
    assert "REF_MARKERS = REF_MARKERS +" not in source

    from core.dialogue import ConversationState, ReferenceResolver, REF_MARKERS
    assert isinstance(REF_MARKERS, tuple)
    assert REF_MARKERS.count("این قسمت") == 1

    state=ConversationState(current_topic="حافظه")
    assert ReferenceResolver().resolve("این قسمت را بهتر کن", state) == "حافظه"


def test_direct_answer_generic_fallback_never_echoes_user_message():
    from types import SimpleNamespace
    from core.dialogue import CognitiveContext, LocalDialogueEngine

    dialogue=SimpleNamespace()
    message="با من مثل یک دستیار عادی حرف بزن"
    context=CognitiveContext(user_message=message)
    answer=LocalDialogueEngine._direct_answer(dialogue,context)

    assert message not in answer
    assert "اگر هدفت ادامه همین موضوع" not in answer
    assert answer == "پیامت رو گرفتم؛ ادامه بده."


def test_tool_router_routes_persian_arithmetic_to_safe_calculator():
    from core.tool_router import ToolRouter
    assert ToolRouter().choose("بیست و پنج ضربدر چهار چند میشه؟") == (None, {})
    assert ToolRouter().choose("۲۵ ضربدر ۴ چند میشه؟") == (
        "calculate", {"expression": "25*4"}
    )
    assert ToolRouter().choose("12 + 8 چند میشه؟") == (
        "calculate", {"expression": "12+8"}
    )


def test_builtin_calculator_is_registered_and_safe(tmp_path):
    from tools.builtin import build_registry

    class Memory:
        def search(self, query, limit):
            return []

    registry=build_registry(tmp_path, Memory())
    assert registry.run("calculate", expression="25*4") == 100
    assert registry.run("calculate", expression="(12+8)/2") == 10
