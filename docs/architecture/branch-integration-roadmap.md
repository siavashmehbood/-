# Architecture and branch integration roadmap

Snapshot date: 2026-09-30  
Repository: `siavashmehbood/-`  
Integration target: `master`  
Active review branch: `codex/canonical-architecture-cleanup` (PR #10)

This roadmap advances every architecture workstream while keeping reviewable changes on pull requests. Branch age is measured against `master`; ahead/behind counts describe commit ancestry, not whether a feature is useful. No branch should be merged solely because it has commits.

## Canonical contracts

| Boundary | Contract |
| --- | --- |
| User turn | `IranRuntime.handle → CognitiveSystem.dispatch → CognitiveSystem.turn → CognitivePipeline.run` owns natural-language execution. |
| Reference and dialogue | Resolve references and update conversation state through the runtime's canonical components; compatibility APIs must not replace runtime owners. |
| Online learning | Evidence creates a proposal; reviewer feedback is tied to that proposal ID; human approval is required before durable offline knowledge, memory, or lessons change. |
| Verification | Component and end-to-end tests exercise Persian input, restart behavior, uncertainty, and safety gates. External reviewer tests use deterministic fixtures unless a live credential is explicitly configured. |

## Branch inventory

| Branch | Relation to master at snapshot | Workstream and next action |
| --- | ---: | --- |
| `codex/canonical-architecture-cleanup` | 23 ahead, 0 behind before this roadmap commit | Primary integration PR. Keep canonical execution, learning lifecycle, and their regression tests together; finish state and direct-answer ownership cleanup, then run Red Team review. |
| `agent-persian-cognition` | 51 ahead, 5 behind | Large Persian cognition delta. Compare each remaining file against current contracts; port only tests or behaviors absent from the canonical branch. |
| `integration/product-acceptance` | 50 ahead, 5 behind | Product acceptance and Persian cross-module regressions. Port useful scenarios into tests against current APIs; do not transplant its older runtime implementation. |
| `agent-gui-integrity` | 3 ahead, 5 behind | GUI integrity. Reconcile with current `gui.py`; bring over only missing UI behavior and cover its runtime calls. |
| `agent-online-learning` | 1 ahead, 5 behind | Online-review safety. Compare against proposal-targeted review and human-approval tests already in PR #10; retain only uncovered cases. |
| `agent-regression-acceptance` | 2 ahead, 5 behind | Regression guidance. Preserve useful failure notes and acceptance criteria, then align them with current CI. |
| `codex/correction-restart-acceptance` | 3 ahead, 1 behind | Its tracked file tree matches `master` at snapshot; no forward port is currently needed. |
| `codex/ci-on-pull-requests` | 2 ahead, 5 behind | CI workflow. Compare triggers and test commands with current workflows before adopting any difference. |
| `ci/persian-conversation-benchmark` | 2 ahead, 300 behind | Historical benchmark work. Re-run its scenarios against the current runtime and port the benchmark contract, not the old runtime snapshot. |
| `feat/iran-cognitive-architecture` | 9 ahead, 300 behind | Historical full-stack architecture. Audit module contracts individually; do not merge the branch wholesale. |
| `feat/real-persian-chat` | 24 ahead, 307 behind | Earlier conversational stack. Treat as a source of test cases and behavior ideas; keep the canonical runtime as execution owner. |
| `refactor/dialogue-canonical` | 18 ahead, 300 behind | Earlier broad cognitive refactor. Harvest isolated, still-missing modules only after dependency and test review. |
| `cognitive-core-1` | 0 ahead, 180 behind | No commits unique to this branch relative to `master`; retain as historical reference. |
| `backup/master-before-canonical-unification` | 0 ahead, 266 behind | Historical backup; preserve unchanged. |
| `backup-before-unify-2026-09-15` | 0 ahead, 351 behind | Historical backup; preserve unchanged. |
| `local-backup-before-unify-2026-09-15` | 0 ahead, 351 behind | Historical backup; preserve unchanged. |

## Delivery sequence

1. **Canonical execution and ownership.** Keep one owner per runtime boundary. Remove remaining method-replacement chains only when behavior can move into the owning class or component with regression coverage.
2. **Persian conversation state.** Validate correction, topic switching, references, compound questions, and restart persistence across the full runtime rather than isolated helpers.
3. **Offline brain and learning.** Keep proposal IDs stable across discovery, review, human approval, durable writes, and restart. Add idempotency and provenance checks before broadening autonomous learning.
4. **Component integration.** Review reasoning, reference intelligence, semantic memory, user model, GUI, and tools against the canonical contracts. Port branch contributions as small, isolated commits.
5. **Acceptance and reliability.** Run unit, integration, runtime-evaluation, CLI, Persian conversation benchmark, and safety suites on each integration PR. Record failures before changing expected behavior.
6. **Release gate.** Perform Red Team review on the final PR head, resolve findings, and confirm branch freshness and required CI before any merge decision.

## Intake rules

- Compare source trees and behavior with the current integration head, not only commit counts.
- Prefer a focused test or a small behavior port over importing a stale branch wholesale.
- Keep external network and model calls out of deterministic tests; live acceptance is a separate opt-in check.
- Do not rewrite or delete backup branches as part of integration.
- Keep changes unmerged until review and the release gate are complete.
