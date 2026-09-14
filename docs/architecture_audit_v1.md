# Iran Cognitive Architecture v1.0 — Phase 0 Audit

Audit date: 2026-09-14
Repository: `C:\IranAI`
Source of truth: user-supplied Iran Cognitive Architecture v1.0

## Baseline
- Python files: 118 (includes sandbox snapshots and audit scripts)
- Production-oriented Python files: ~64 checked by runtime evaluator
- Test files: 10 after this audit
- Python lines: 5,134 including sandbox/tests
- Classes: 125
- Functions: 517
- Regression suite: 33 tests, all passing
- Compile check: 66 files checked by evaluator, all passing
- Behavioral benchmark: 0.969, passing
- External model: not used by the active local provider

## Architecture coverage
| Capability | Current state | Assessment |
|---|---|---|
| Observe | Runtime events, world observations, tool results | Partial/working |
| Understand | AdvancedLanguage + Brain + discourse context | Working but symbolic |
| Remember | SQLite episodic-like store + semantic facts + lessons | Partial; temporal layer added |
| Model | WorldModel + KnowledgeGraph | Partial |
| Reason | hypotheses + evidence graph + causal/counterfactual layer | Working baseline |
| Predict | empirical PredictionEngine | Working baseline; calibration needs real outcomes |
| Goals | GoalStore + goal tools | Working baseline |
| Plan | Planner with dependencies and 5-stage plans | Working baseline |
| Decide | DecisionEngine + confidence/risk signals | Working baseline |
| Act | Tool Registry/Router + policy gate | Partial; execution loop is bounded |
| Observe Result | score/world transition/reflection | Working baseline |
| Evaluate | Evaluator + behavioral benchmark | Working |
| Reflect | ReflectionEngine + post-action reflection | Working |
| Learn | experience store + rules + semantic consolidation | Working baseline; needs causal learning |
| Improve | sandbox snapshot/benchmark/rollback | Partial; candidate generation is not yet autonomous code synthesis |
| Self-heal | diagnostics/rollback pieces | Partial; no production repair allowed |

## Findings
1. The core loop exists, but several modules are still wrappers around deterministic heuristics rather than learned models.
2. Memory was the largest functional gap: retrieval was mostly lexical/recency based and could not reliably honor `دیروز/امروز`.
3. The repository has no dependency manifest (`requirements.txt`, `pyproject.toml`, etc.). Reproducibility is therefore weaker than required.
4. README version is stale (`0.9.0`) while runtime config has advanced beyond it.
5. Four syntax-invalid files exist inside sandbox/archive material because of UTF-8 BOM handling. Production evaluator currently excludes them from its checked set, but repository hygiene should be fixed.
6. GUI still contains two explicit `pass` handlers and should not be considered a completed interaction surface without end-to-end GUI tests.
7. Network-capable modules exist (`providers/remote.py`, `web_fetch`), but the active local provider remains offline. Security policy correctly blocks shell and write by default.
8. Prediction currently reports many 1.0 rates because the recorded outcome is tied to response score, not independently verified task success. This is an evaluation-design weakness.
9. WorldModel currently records many events/observations but has zero durable entities/relations in the latest snapshot; world modeling is therefore underutilized.
10. The current benchmark is strong on component behavior but still weak on long-horizon multi-turn tasks, memory recall accuracy, replanning after failed actions, and learning transfer.

## Immediate priority
The highest-value next capability is a real episodic-to-semantic learning loop:
`Episode -> temporal/topic retrieval -> validated evidence -> lesson -> strategy update -> future decision -> independently verified outcome`.

The first implementation step has been completed in this audit: `memory/episodic.py` adds explicit time-scoped retrieval and is wired into the cognitive cycle.
