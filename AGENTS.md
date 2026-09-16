# AGENTS.md

Repository knowledge for agents working on IRAN.

## What this project is

A fully offline Persian cognitive architecture: dialogue, memory, knowledge graph,
reasoning and autonomy. Standard library only — no external AI, API, pretrained model or
embedding service. There is no `requirements.txt`; the runtime is stdlib plus tkinter.
Preserve that constraint. Do not add network calls or external model dependencies.

## Commands

```bash
# Full test suite
python3 -m unittest discover -s tests -q

# Single module
python3 -m unittest tests.test_answer_hygiene -v

# Conversation benchmark + audit (threshold 100.0, no exempt categories)
python3 scripts/run_conversation_audit.py

# Compile check
python3 -m compileall -q core memory knowledge learning tools runtime
```

To run code against a temporary runtime root, `PYTHONPATH` must include the project root
when the script lives outside it. Runtime tests build a temp root by copying
`config.json` and pointing `memory.db`, `runtime.event_log` and `runtime.goals` inside it.

## Layout

| Path | Role |
|---|---|
| `core/` | Dialogue, routing, cognition, rules, self-awareness |
| `memory/` | SQLite-backed episodic, semantic and working memory |
| `knowledge/` | Durable knowledge graph (`data/knowledge_graph.json`) |
| `learning/` | Procedural memory and skills |
| `runtime/` | Application assembly and the `IranRuntime` facade |
| `tools/` | Tool registry and built-in tools |
| `self/` | Benchmarks, diagnostics, roadmap evaluation |
| `benchmarks/` | Persian conversation benchmark (100 scenarios, 10 categories) |
| `tests/` | `unittest` suites, run with `discover -s tests` |
| `docs/` | Subsystem documentation |

## Conventions

- Tests use `unittest`, not pytest. Discovery is by module path under `tests/`.
- Persistent stores write atomically; the knowledge graph goes through
  `persistence.atomic_write_json`.
- Answer hygiene is a hard rule: internal analysis and pipeline vocabulary must never
  reach a user-visible reply. `tests/test_answer_hygiene.py` enforces this across all
  100 benchmark answers. See `docs/conversation.md`.
- Validators report and never repair. Silent repair hides corruption. Both
  `Memory.validate()` and `KnowledgeGraph.validate()` are tested for this.
- Destructive memory operations require an explicit criterion; `Memory.forget()` raises
  when called with none.

## Traps found the hard way

- **Duplicate `ConversationState`.** `core/dialogue.py` and `core/conversation_state.py`
  both define one, with different fields. The runtime uses the `core/dialogue.py` class;
  `core/agent.py` uses the other. They are not interchangeable. Check which one you are
  holding before assuming a field exists.
- **`ConversationState.update()` returns the live stored record.** Mutating the result
  mutates the persisted state.
- **`ProceduralMemory.upsert()` now returns a snapshot.** It used to return the live dict,
  so a held result changed under later revisions.
- **Monkeypatch composition.** `runtime/app.py` is a large file whose behaviour is
  assembled from many runtime reassignments of `IranRuntime` and `LocalDialogueEngine`
  methods. The intended order is declared in `runtime/composition.py` (`LAYER_ORDER`,
  `tests/test_runtime_composition.py` guards it). When editing the runtime, read that
  file first — reordering layers changes behaviour.
- **Benchmark, not thresholds.** If the conversation benchmark drops, find the cause.
  Do not lower `TARGET` in `scripts/run_conversation_audit.py`.

## Git

- `master` is canonical. Do not merge or replace existing open PRs.
- Feature work happens on `feat/iran-cognitive-architecture`, based on the
  benchmark/CI branch, which is based on `master`.
- CI runs on push, all branches (`branches: ['**']`). A `'*'` pattern silently misses
  branches containing `/`.
