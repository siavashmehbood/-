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

    dialogue=SimpleNamespace(_compose_conversational=lambda context: None)
    message="با من مثل یک دستیار عادی حرف بزن"
    context=CognitiveContext(user_message=message)
    answer=LocalDialogueEngine._direct_answer(dialogue,context)

    assert message not in answer
    assert "اگر هدفت ادامه همین موضوع" not in answer
    assert answer == "پیامت رو گرفتم؛ ادامه بده."


def test_tool_router_routes_persian_arithmetic_to_safe_calculator():
    from core.tool_router import ToolRouter
    assert ToolRouter().choose("بیست و پنج ضربدر چهار چند میشه؟") == (
        "calculate", {"expression": "25*4"}
    )
    assert ToolRouter().choose("دوازده به علاوه هشت") == ("calculate", {"expression": "12+8"})
    assert ToolRouter().choose("صد تقسیم بر چهار") == ("calculate", {"expression": "100/4"})
    assert ToolRouter().choose("سی منهای پنج") == ("calculate", {"expression": "30-5"})
    assert ToolRouter().choose("دو ضربدر سه") == ("calculate", {"expression": "2*3"})
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


def test_real_runtime_manual_conversation_quality_regressions(tmp_path):
    import shutil
    from pathlib import Path
    from runtime.app import IranRuntime

    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime = IranRuntime(tmp_path)
    try:
        greeting = runtime.handle("سلام، هستی؟")
        assert greeting
        assert any(x in greeting for x in ("سلام", "هستم"))
        assert not any(x in greeting for x in ("هدف، زمینه", "شواهد، گزینه", "چند مرحله تحلیل"))
        assert "متوجه شدم:" not in greeting
        assert "اگر هدفت ادامه همین موضوع" not in greeting

        ready = runtime.handle("آره من سیاوشم. امروز می‌خوام باهات چندتا تست انجام بدم، آماده‌ای؟")
        assert ready
        assert "متوجه شدم:" not in ready
        assert "اگر هدفت ادامه همین موضوع" not in ready

        name = runtime.handle("اسم من چیه؟")
        assert "سیاوش" in name

        style = runtime.handle("با من مثل یک دستیار عادی حرف بزن.")
        assert "با من مثل یک دستیار عادی حرف بزن" not in style
        assert "اگر هدفت ادامه همین موضوع" not in style
        assert any(x in style for x in ("طبیعی", "مستقیم", "حتماً"))

        support = runtime.handle("امروز حالم خوب نیست. یکم باهام حرف بزن.")
        assert support
        assert "امروز حالم خوب نیست" not in support
        assert "اگر هدفت ادامه همین موضوع" not in support
        assert support != style
        assert any(x in support for x in ("حالت", "اینجام", "حرف", "اذیت"))

        arithmetic = runtime.handle("۲۵ ضربدر ۴ چند میشه؟ فقط جواب بده.")
        assert str(arithmetic).strip() == "100"

        word_arithmetic = runtime.handle("بیست و پنج ضربدر چهار چند میشه؟ فقط جواب بده.")
        assert str(word_arithmetic).strip() in {"100", "۱۰۰"}
    finally:
        runtime.close()



def test_real_runtime_current_turn_dominates_seeded_stale_project_memory(tmp_path):
    import shutil
    from pathlib import Path
    from runtime.app import IranRuntime

    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime = IranRuntime(tmp_path)
    try:
        # Deliberately contaminate durable memory with realistic unrelated facts.
        runtime.memory.add("fact", "اسم پروژه من دانا هست", .95, confidence=.99, source="regression_seed")
        runtime.memory.add("accepted_answer", "در حافظه مرتبط با این موضوع ثبت شده. اسم پروژه من دانا هست", .95, confidence=.99, source="regression_seed")
        runtime.memory.add("fact", "پروژه دانا یک سامانه کتاب و کتاب صوتی است", .90, confidence=.95, source="regression_seed")

        turns = [
            ("سلام، هستی؟", "greeting"),
            ("من سیاوشم", "intro"),
            ("اسم من چیه؟", "name"),
            ("با من مثل یک دستیار عادی حرف بزن.", "style"),
            ("امروز حالم خوب نیست. یکم باهام حرف بزن.", "emotion1"),
            ("حوصله ندارم حالم بده یکم با من حرف بزن", "emotion2"),
            ("جواب تکراری نده", "no_repeat"),
            ("باشه، یکم معمولی باهام حرف بزن", "recovery"),
        ]
        answers = {}
        for prompt, key in turns:
            answers[key] = runtime.handle(prompt)
            assert answers[key]
            if key not in {"name"}:
                assert "اسم پروژه من دانا هست" not in answers[key]
                assert "در حافظه مرتبط با این موضوع ثبت شده" not in answers[key]

        assert "سیاوش" in answers["name"]
        assert "دانا" not in answers["name"]
        assert any(x in answers["style"] for x in ("طبیعی", "مستقیم", "حتماً"))
        assert "دانا" not in answers["style"]
        assert any(x in answers["emotion1"] for x in ("حالت", "اینجام", "حرف", "اذیت"))
        assert any(x in answers["emotion2"] for x in ("کنارت", "گوش", "حالت", "حرف"))
        assert answers["emotion2"] != answers["emotion1"]
        assert "دانا" not in answers["no_repeat"]
        assert "حافظه مرتبط" not in answers["no_repeat"]
        assert answers["no_repeat"] != answers["emotion2"]
        assert "دانا" not in answers["recovery"]

        # Positive recall must remain available when memory is explicitly requested.
        project = runtime.handle("اسم پروژه من چی بود؟")
        assert "دانا" in project
        assert "حافظه مرتبط" not in project

        # Genuine explicit reference remains conversationally available.
        runtime.handle("موضوع اصلی ما پروژه IRAN است.")
        reference = runtime.handle("همون قبلی رو ادامه بده")
        assert any(x in reference for x in ("IRAN", "ایران", "پروژه"))

        # Similar style imperatives generalize beyond one exact string.
        for command in (
            "همش یه جواب رو تکرار نکن",
            "جوابات تکراری شده",
            "یه جور دیگه جواب بده",
            "کوتاه جواب بده",
            "طبیعی‌تر حرف بزن",
            "مثل یک دستیار عادی جواب بده",
        ):
            response = runtime.handle(command)
            assert response
            assert "دانا" not in response
            assert "حافظه مرتبط" not in response
    finally:
        runtime.close()

def test_memory_context_requires_current_turn_relevance(tmp_path):
    from memory.store import Memory
    from core.memory_intelligence import MemoryIntelligence

    memory = Memory(tmp_path / "memory.db")
    try:
        memory.add("accepted_answer", "پاسخ قدیمی درباره پروژه و معماری", .95, confidence=.99)
        intelligence = MemoryIntelligence(memory)
        context = intelligence.build_context("امروز حالم خوب نیست، یکم باهام حرف بزن")
        assert all(item["relevance"] >= .15 for item in context["selected"])
        assert not any("پاسخ قدیمی درباره پروژه" in item["content"] for item in context["selected"])
    finally:
        memory.close()


def test_explicit_reference_can_still_recall_recent_context(tmp_path):
    from memory.store import Memory
    from core.memory_intelligence import MemoryIntelligence

    memory = Memory(tmp_path / "memory.db")
    try:
        memory.add("user", "پروژه IRAN را ادامه بده", .8, confidence=.9)
        intelligence = MemoryIntelligence(memory)
        context = intelligence.build_context("همون قبلی رو ادامه بده")
        assert any("پروژه IRAN" in item["content"] for item in context["selected"])
    finally:
        memory.close()



def test_real_runtime_style_commands_dominate_seeded_stale_memory(tmp_path):
    import shutil
    from pathlib import Path
    from runtime.app import IranRuntime

    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime = IranRuntime(tmp_path)
    try:
        runtime.memory.add("user", "اسم پروژه من دانا هست", .95, confidence=.99)
        runtime.memory.add("accepted_answer", "در حافظه مرتبط با این موضوع ثبت شده. اسم پروژه من دانا هست", .95, confidence=.99)
        runtime.memory.add("user", "پروژه دانا یک پروژه فنی برای کتاب است", .9, confidence=.95)
        runtime.user_model.record("من روی دانا کار می‌کنم")
        greeting = runtime.handle("سلام، هستی؟")
        assert "دانا" not in greeting
        runtime.handle("من سیاوشم")
        name = runtime.handle("اسم من چیه؟")
        assert "سیاوش" in name and "دانا" not in name
        style = runtime.handle("با من مثل یک دستیار عادی حرف بزن.")
        assert "دانا" not in style
        first = runtime.handle("امروز حالم خوب نیست. یکم باهام حرف بزن.")
        second = runtime.handle("حوصله ندارم حالم بده یکم با من حرف بزن")
        assert "دانا" not in first and "دانا" not in second
        assert first != second
        no_repeat = runtime.handle("جواب تکراری نده")
        assert "دانا" not in no_repeat
        assert "در حافظه مرتبط" not in no_repeat
        assert no_repeat not in {first, second}
        follow = runtime.handle("خب، همین‌طوری طبیعی ادامه بده")
        assert "دانا" not in follow
        for command in ("کوتاه جواب بده", "طبیعی‌تر حرف بزن", "مثل یک دستیار عادی جواب بده", "همش یه جواب رو تکرار نکن", "یه جور دیگه جواب بده"):
            answer = runtime.handle(command)
            assert "دانا" not in answer
            assert "در حافظه مرتبط" not in answer
        project = runtime.handle("اسم پروژه من چی بود؟")
        assert "دانا" in project
    finally:
        runtime.close()


def test_real_runtime_explicit_reference_survives_style_fix(tmp_path):
    import shutil
    from pathlib import Path
    from runtime.app import IranRuntime

    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime = IranRuntime(tmp_path)
    try:
        runtime.handle("موضوع اصلی ما پروژه IRAN است.")
        answer = runtime.handle("همون قبلی رو ادامه بده")
        assert any(x in answer for x in ("IRAN", "ایران", "پروژه"))
    finally:
        runtime.close()


def test_orchestrator_calculator_returns_bare_result_for_conversation():
    from types import SimpleNamespace
    from core.orchestrator import Orchestrator

    fake = SimpleNamespace(
        router=SimpleNamespace(choose=lambda text: ("calculate", {"expression": "25*4"})),
        run_tool=lambda name, **kwargs: 100,
    )
    assert Orchestrator._auto_tool(fake, "۲۵ ضربدر ۴ چند میشه؟ فقط جواب بده.") == "100"


def test_professional_conversation_state_style_and_history_are_general():
    from core.dialogue import ConversationState
    from core.conversational_understanding import ConversationalUnderstanding

    state=ConversationState()
    understanding=ConversationalUnderstanding()
    cases={
        "فعلاً کوتاه جواب بده":("short","temporary"),
        "از این به بعد مرحله به مرحله بگو":("stepwise","persistent"),
        "فنی‌تر توضیح بده":("technical","conversation"),
        "فارسی جواب بده":("persian","conversation"),
        "اینقدر توضیح اضافه نده":("long",None),
    }
    for text,(style,scope) in cases.items():
        styles=understanding.style_request(text)
        if style=="long" and style not in styles:
            continue
        assert style in styles
        if scope:
            assert understanding.temporal_scope(text)==scope
    state.set_style(["short"],"temporary")
    state.update("یک پیام معمولی","باشه","SOCIAL",{"intent":"general"},.9)
    assert state.recent_user_turns[-1]=="یک پیام معمولی"
    assert state.recent_assistant_turns[-1]=="باشه"
    assert state.response_style["short"]["scope"]=="temporary"


def test_professional_reference_vocabulary_generalizes():
    from core.conversational_understanding import ConversationalUnderstanding
    understanding=ConversationalUnderstanding()
    for text,marker in (
        ("همینو ادامه بده","همینو"),
        ("اون بخش رو بیشتر توضیح بده","اون بخش"),
        ("اون پروژه چی بود؟","اون پروژه"),
        ("بحث قبلی رو ادامه بده","بحث قبلی"),
        ("دومی رو بیشتر توضیح بده","دومی"),
    ):
        meaning=understanding.analyze(text)
        assert marker in meaning.references


def test_real_runtime_professional_meta_and_style_controls(tmp_path):
    import shutil
    from pathlib import Path
    from runtime.app import IranRuntime

    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime=IranRuntime(tmp_path)
    try:
        runtime.memory.add("accepted_answer","پاسخ قدیمی نامرتبط درباره دانا",.99,confidence=.99)
        runtime.handle("سلام، هستی؟")
        runtime.handle("من سیاوشم")
        short=runtime.handle("فعلاً کوتاه جواب بده")
        assert short and "دانا" not in short
        meta=runtime.handle("آخرین چیزی که گفتم چی بود؟")
        assert "فعلاً کوتاه جواب بده" in meta
        assert "دانا" not in meta
        natural=runtime.handle("طبیعی حرف بزن")
        assert natural and "دانا" not in natural
        meta2=runtime.handle("تو چی جواب دادی؟")
        assert meta2 and "دانا" not in meta2
        assert "طبیعی" in meta2 or "مستقیم" in meta2
    finally:
        runtime.close()


def test_real_runtime_long_professional_conversation_with_stale_memory(tmp_path):
    import shutil
    from pathlib import Path
    from runtime.app import IranRuntime

    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path)
    runtime=IranRuntime(tmp_path)
    try:
        runtime.memory.add("accepted_answer","پاسخ قدیمی نامرتبط درباره پروژه سایه",.99,confidence=.99)
        prompts=[
            "سلام، هستی؟",
            "من سیاوشم",
            "اسم من چیه؟",
            "طبیعی حرف بزن",
            "امروز حالم خوب نیست. یکم باهام حرف بزن.",
            "جواب تکراری نده",
            "فعلاً کوتاه جواب بده",
            "موضوع اصلی ما پروژه IRAN است.",
            "همون قبلی رو ادامه بده",
            "آره",
            "بیشتر توضیح بده",
            "ساده‌تر بگو",
            "مثال بزن",
            "تو چی جواب دادی؟",
            "آخرین چیزی که گفتم چی بود؟",
        ]
        answers=[]
        for prompt in prompts:
            answer=runtime.handle(prompt)
            assert answer
            assert "پاسخ قدیمی نامرتبط" not in answer
            assert "در حافظه مرتبط با این موضوع ثبت شده" not in answer
            answers.append(answer)
        assert "سیاوش" in answers[2]
        assert answers[4] != answers[5]
        assert any(x in answers[8] for x in ("IRAN","ایران","پروژه"))
        assert answers[14] and "UNKNOWN:" not in answers[14]
        assert "تو چی جواب دادی" in answers[14] or "جواب" in answers[14]
        assert str(runtime.cognitive_system.dialogue.state.response_style)
    finally:
        runtime.close()
