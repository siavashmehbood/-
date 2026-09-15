# Iran — Phase 0 Repository Audit (cognitive architecture mission)

Audit date: 2026-09-15
Branch: `feat/iran-cognitive-architecture` (based on `master` + benchmark/CI work)
Baseline commit: `d8553c0`
Baseline test result: **173 tests, OK**

## Git state at audit time
- `origin/master` = `37796c4` — untouched, not modified by this work.
- PR #1 (`feat/real-persian-chat`) — untouched, still open.
- Development branch contains no merge of PR #1.

## Repository shape
| Metric | Value |
|---|---|
| Python files | 139 |
| Python lines | ~12,100 |
| Test files | 47 |
| Baseline tests | 173 passing |
| External AI dependencies | **none** |

## Offline guarantee — verified
A scan for `openai`, `anthropic`, `claude`, `gemini`, `deepseek`, `ollama`, `llama`,
`qwen`, `mistral`, `transformers`, `huggingface`, `sentence_transformers`, embedding
APIs and outbound HTTP calls found **no AI-service dependency**. All imports resolve
to the standard library (`sqlite3`, `re`, `json`, `tkinter`, `urllib`, ...) plus
in-repository packages. `config.json` declares `model.provider = "iran"` with
`mode = "offline-symbolic"`. The only network-capable code path is the explicit
`web_fetch` tool, gated behind `security.allow_network_tools`.

## Capability audit — what already exists

The mission brief lists many subsystems as targets. Most already exist. Per the
NO REINVENTION rule they must be extended, not rebuilt.

| Target subsystem | Existing implementation | Real state |
|---|---|---|
| Conversation context | `core/conversation_state.py`, `core/dialogue.py` | Working, canonical |
| Working / short-term memory | `Memory.working_context`, `Memory.recent` | Working |
| Episodic memory | `memory/episodic.py` + `memories` table | Working, time-scoped retrieval |
| Semantic memory | `memory/semantic.py` + `semantic_facts` table | Working |
| Procedural memory | `learning/procedural_memory.py`, `learning/skill_system.py` | Working, versioned, precondition checks |
| Knowledge graph | `knowledge/knowledge_graph.py` | Working: nodes, edges, `infer`, `contradictions` |
| Reasoning | `core/reasoning.py`, `core/reasoning_graph.py` (multi-hop), `core/rule_engine.py` (forward chaining + `explain`) | Working baseline |
| Goals | `runtime/goals.py`, `core/autonomous_goal_runner.py` | Working |
| Planning | `planning/planner.py` (steps, deps, replan, rollback) | Working |
| Prediction / decision | `core/prediction.py`, `core/decision.py` | Working baseline |
| Tool routing | `core/tool_router.py`, `tools/registry.py`, `security/policy.py` | Working, **one defect — see below** |
| Observation / verification | `core/observation.py`, `core/verification.py` | Working |
| Failure / replanning | `core/failure.py`, `core/replanning.py`, `core/recovery_orchestrator.py` | Working |
| Self-repair | `core/recovery_orchestrator.py`, `core/self_awareness.py` | Partial, bounded |
| Learning | `learning/learning_engine.py`, `core/reflection.py` | Working, symbolic |
| Persian language | `language_intelligence.py`, `core/language_engine.py`, `core/cognitive_fabric.py` | Working |
| Persistence | SQLite + JSON stores throughout; `persistence.py` | Working |
| Runtime / CLI | `runtime/app.py`, `main.py`, `gui.py`, `iran_gui.pyw` | Working |
| Simulation | `core/virtual_world.py`, `core/world_model.py` | Working |

## Findings

### F1 — The real architectural debt is patch layering, not missing subsystems
`runtime/app.py` is 1,516 lines and contains **71 monkeypatch assignments**, of which
**22 overwrite `IranRuntime.handle`** and **13 overwrite `IranRuntime.__init__`**. The
same pattern repeats in library modules: `planning/planner.py` has `_build_v2`,
`_build_v3`, `_build_v4`, `_build_v31`, `_build_v31b`; `memory/store.py` patches
`Memory.search` as `_search_v2`; `knowledge/knowledge_graph.py` patches `add_fact`;
`core/dialogue.py` carries several `_*_v31` layers.

This is the highest-risk thing in the repository. The effective behaviour of
`Runtime.handle` is defined by the *order* of 22 assignments and is not readable from
any single function. Assignment order is load-bearing and undefended by tests.

Remediation direction (chosen because it is additive and reversible):
`runtime/composition.py` declares the canonical layer order as explicit data, with a
contract test asserting every `handle` patch site in `app.py` is either registered
there or explicitly allow-listed. No behaviour moves and no patch is removed in the
first step.

### F2 — `unknown` routing gap (real product defect)
`core/tool_router.py` diverts a turn to the clock tool on the bare token `ساعت`:

```
ToolRouter().choose('آیا فردا ساعت ۸ باران می‌بارد؟')  -> ('time_now', {})
```

The dialogue layer answers this correctly; the router pre-empts it:

```
runtime.handle(...)   -> 'زمان سیستم: 2026-09-15T23:44:34'
runtime.dialogue.handle(...) -> 'UNKNOWN: برای این سؤال ... اطلاعات کافی ندارم ...'
```

So the honesty system is implemented and correct; it is being bypassed. This causes
10 of the 10 remaining benchmark failures (`unknown_1..10`) and is the current
priority. Fix is scoped to yes/no (`آیا`) questions so the clock route for genuine
time requests (`ساعت الان چند است`, `ساعت را بگو`, `زمان سیستم`) is untouched.

### F3 — A weak test masked F2
`tests/test_conversation_output.py::test_unknown_is_honest` asserts only
`assertNotIn('حتماً', answer)`. The unrelated clock output satisfies that. The test
passed while the honesty path was unreachable. Strengthened to assert the honest
refusal is actually present.

### F4 — Obfuscated literals at the runtime boundary
The final guard block in `app.py` builds Persian strings from `chr()` code points
(9 `_fa(...)` calls), which makes the user-facing contract unreadable. Contradicts the
project's own rule that internal analysis must not leak into user-facing output.

### F5 — No dependency manifest
No `requirements.txt` / `pyproject.toml`. README states version 0.28.0 while
`config.json` states 0.46.0.

## Immediate priority
Fix F2 (real product defect, blocks the benchmark target), then strengthen the test
that hid it (F3). Then begin F1 remediation, which is the durable architectural win.
