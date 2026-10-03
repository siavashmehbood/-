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


def test_dialogue_cleanup_preserves_non_handle_runtime_adapters():
    source=Path("core/dialogue.py").read_text(encoding="utf-8")
    # These adapters affect state/retrieval/reasoning used by the canonical
    # pipeline; the cleanup must remove only dead handle wrappers.
    assert "LocalDialogueEngine.__init__ = _chain_init" in source
    assert "LocalDialogueEngine._memory = _memory_chain_context" in source
    assert "ReferenceResolver.resolve = _reference_resolve_v2" in source
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
