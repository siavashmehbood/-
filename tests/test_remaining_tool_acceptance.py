"""Recover outstanding historical behavior without merging obsolete branches."""
import pytest
from pathlib import Path

def test_dialogue_memory_filter_omits_current_query_and_keeps_context():
    from types import SimpleNamespace
    from core.dialogue import LocalDialogueEngine

    calls=[]
    class Memory:
        def working_context(self,text,limit):
            calls.append((text,limit))
            return [
                ("user","  پرسش فعلی  "),
                ("assistant","پاسخ قبلی"),
                ["user","پرسش فعلی"],
                {"kind":"memory","content":"زمینه ساختاریافته"},
            ]

    dialogue=SimpleNamespace(runtime=SimpleNamespace(memory=Memory()))
    rows=LocalDialogueEngine._memory(dialogue,"پرسش فعلی")
    assert rows == [
        ("assistant","پاسخ قبلی"),
        {"kind":"memory","content":"زمینه ساختاریافته"},
    ]
    assert calls == [("پرسش فعلی",12)]

    class BrokenMemory:
        def working_context(self,text,limit):
            raise RuntimeError("memory unavailable")

    broken=SimpleNamespace(runtime=SimpleNamespace(memory=BrokenMemory()))
    assert LocalDialogueEngine._memory(broken,"پرسش فعلی") == []


def test_orchestrator_records_tool_failures_and_reraises_original_exception():
    from types import SimpleNamespace
    from core.orchestrator import Orchestrator

    expected = ValueError("calculator exploded")
    emitted = []
    recorded = []

    class FailingRegistry:
        def get(self, name):
            return SimpleNamespace(permission="read")

        def run(self, name, **kwargs):
            raise expected

    fake = SimpleNamespace(
        registry=FailingRegistry(),
        policy=None,
        events=SimpleNamespace(
            emit=lambda event, payload: emitted.append((event, payload))
        ),
        metrics=SimpleNamespace(record=recorded.append),
    )

    with pytest.raises(ValueError) as caught:
        Orchestrator.run_tool(fake, "calculate", expression="1/0")

    assert caught.value is expected
    assert recorded == ["tool_failed"]
    assert emitted == [(
        "tool_failed",
        {
            "tool": "calculate",
            "ok": False,
            "error": "ValueError",
            "stage": "execution",
        },
    )]
    assert "expression" not in emitted[0][1]
    assert "message" not in emitted[0][1]

    fake.events = SimpleNamespace(
        emit=lambda event, payload: (_ for _ in ()).throw(
            RuntimeError("event sink unavailable")
        )
    )
    with pytest.raises(ValueError) as caught_again:
        Orchestrator.run_tool(fake, "calculate", expression="secret")
    assert caught_again.value is expected
    assert recorded == ["tool_failed", "tool_failed"]



def test_orchestrator_records_lookup_and_permission_failures():
    from types import SimpleNamespace
    from core.orchestrator import Orchestrator

    emitted = []
    recorded = []
    metrics = SimpleNamespace(record=recorded.append)
    events = SimpleNamespace(
        emit=lambda event, payload: emitted.append((event, payload))
    )

    unknown = SimpleNamespace(
        registry=None,
        policy=None,
        events=events,
        metrics=metrics,
    )
    with pytest.raises(KeyError, match="unknown tool: missing"):
        Orchestrator.run_tool(unknown, "missing")
    assert emitted.pop() == (
        "tool_failed",
        {
            "tool": "missing",
            "ok": False,
            "error": "KeyError",
            "stage": "lookup",
        },
    )
    assert recorded == ["tool_failed"]

    execution_calls = []
    registry = SimpleNamespace(
        get=lambda name: SimpleNamespace(permission="network"),
        run=lambda name, **kwargs: execution_calls.append((name, kwargs)),
    )
    denied = SimpleNamespace(
        registry=registry,
        policy=SimpleNamespace(allows=lambda permission: False),
        events=events,
        metrics=metrics,
    )
    with pytest.raises(PermissionError, match="permission denied: network"):
        Orchestrator.run_tool(denied, "remote_lookup", query="private")
    assert execution_calls == []
    assert emitted == [(
        "tool_failed",
        {
            "tool": "remote_lookup",
            "ok": False,
            "error": "PermissionError",
            "stage": "permission",
        },
    )]
    assert "query" not in emitted[0][1]
    assert "message" not in emitted[0][1]
    assert recorded == ["tool_failed", "tool_failed"]
    assert "tool" not in recorded




def test_real_metrics_snapshot_separates_tool_success_and_failure():
    from types import SimpleNamespace
    from core.metrics import Metrics
    from core.orchestrator import Orchestrator

    class Registry:
        def get(self, name):
            return SimpleNamespace(permission="read")

        def run(self, name, **kwargs):
            if name == "broken":
                raise ValueError("sensitive failure detail")
            return "ok"

    metrics = Metrics()
    fake = SimpleNamespace(
        registry=Registry(),
        policy=None,
        events=SimpleNamespace(emit=lambda event, payload: None),
        metrics=metrics,
    )

    assert Orchestrator.run_tool(fake, "healthy") == "ok"
    with pytest.raises(ValueError, match="sensitive failure detail"):
        Orchestrator.run_tool(fake, "broken")

    snapshot = metrics.snapshot()
    assert snapshot["events"] == {"tool": 1, "tool_failed": 1}
    assert "sensitive failure detail" not in repr(snapshot)



def test_orchestrator_returns_success_when_telemetry_sinks_fail():
    from types import SimpleNamespace
    from core.orchestrator import Orchestrator

    execution_calls = []
    recorded = []

    registry = SimpleNamespace(
        get=lambda name: SimpleNamespace(permission="read"),
        run=lambda name, **kwargs: execution_calls.append((name, kwargs)) or "ok",
    )
    event_failure = SimpleNamespace(
        registry=registry,
        policy=None,
        events=SimpleNamespace(
            emit=lambda event, payload: (_ for _ in ()).throw(
                RuntimeError("event sink unavailable")
            )
        ),
        metrics=SimpleNamespace(record=recorded.append),
    )

    assert Orchestrator.run_tool(event_failure, "healthy", value="private") == "ok"
    assert recorded == ["tool"]

    emitted = []
    metric_failure = SimpleNamespace(
        registry=registry,
        policy=None,
        events=SimpleNamespace(
            emit=lambda event, payload: emitted.append((event, payload))
        ),
        metrics=SimpleNamespace(
            record=lambda event: (_ for _ in ()).throw(
                RuntimeError("metrics sink unavailable")
            )
        ),
    )

    assert Orchestrator.run_tool(metric_failure, "healthy") == "ok"
    assert emitted == [(
        "tool_executed",
        {"tool": "healthy", "ok": True},
    )]
    assert execution_calls == [
        ("healthy", {"value": "private"}),
        ("healthy", {}),
    ]

@pytest.mark.parametrize("text,expression", [
    ("  بیست   و   پنج   ضربدر   چهار  ", "25*4"),
    ("دوازده\tبه علاوه\nهشت", "12+8"),
    ("٢٥ ضربدر ٤", "25*4"),
])
def test_arithmetic_whitespace_and_arabic_digits(text, expression):
    from core.tool_router import ToolRouter
    assert ToolRouter().choose(text) == ("calculate", {"expression":expression})

@pytest.mark.parametrize("text", ["تاریخ ۲۰۲۶-۱۰-۰۳ چیست؟", "ساعت ۱۲ + ۸ را بگو"])
def test_time_intent_precedes_numeric_extraction(text):
    from core.tool_router import ToolRouter
    assert ToolRouter().choose(text) == ("time_now", {})

def test_calculator_bounds_and_valid_numbers(tmp_path):
    from types import SimpleNamespace
    from tools.builtin import build_registry
    registry = build_registry(tmp_path, SimpleNamespace(search=lambda *a: []))
    assert registry.run("calculate", expression="٢٥ * ٤") == 100
    assert registry.run("calculate", expression="(12+8)/2") == 10
    for expression, reason in [
        ("1/0", "تقسیم بر صفر"), ("10**1000000", "توان خارج از محدوده"),
        ("2 +", "نامعتبر"), ("1e309", "خارج از محدوده"),
        ("9"*129, "بیش از حد طولانی"), ("(-1)**0.5", "عدد حقیقی"),
    ]:
        with pytest.raises(ValueError, match=reason):
            registry.run("calculate", expression=expression)

def test_calculator_validation_is_user_facing_and_unexpected_failures_propagate():
    from types import SimpleNamespace
    from core.orchestrator import Orchestrator
    fake = SimpleNamespace(router=SimpleNamespace(choose=lambda text: ("calculate", {})),
                           run_tool=lambda *a, **kw: (_ for _ in ()).throw(ValueError("عبارت نامعتبر")))
    assert Orchestrator._auto_tool(fake, "2 +") == "محاسبه انجام نشد: عبارت نامعتبر"
    fake.run_tool = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("broken"))
    with pytest.raises(RuntimeError, match="broken"):
        Orchestrator._auto_tool(fake, "2 +")
