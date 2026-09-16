# IRAN Cognitive Core Migration Plan

## Purpose

This document defines the migration from the current multi-layer dialogue/cognition implementation toward one canonical cognitive core. The existing system is preserved; this is a controlled consolidation, not a destructive rewrite.

## Current baseline

The master baseline is commit `37796c4898b4ad96272181d7a6961186f37ed348`.
PR #3 is a separate branch and is 18 commits ahead of master. It is not part of master.

## Canonical target

```text
Input
  -> Perception / Persian parsing
  -> Conversation State
  -> Reference resolution
  -> Memory + Knowledge retrieval
  -> Evidence normalization
  -> Reasoning / contradiction detection
  -> Decision / response plan
  -> Response realization
  -> Verification / repair
  -> Commit memory + learning
  -> Output
```

Exactly one visible response path should own this cycle.

## Keep

- Persian language intelligence
- conversation state and reference handling
- working/episodic/semantic memory
- knowledge graph
- symbolic reasoning and chain reasoning
- verification and repair
- user model
- event/observability infrastructure
- existing UI/runtime as an interface layer

## Freeze during core stabilization

- autonomous supervisor/daemon work
- multi-agent expansion
- phone/voice/vision/browser automation
- virtual-world expansion
- additional self-improvement mechanisms

These are not removed. They are out of scope until the core conversation contract is stable.

## Refactoring rules

1. No new response path may bypass the canonical cognitive cycle.
2. Compatibility adapters may exist only at the boundary and must not contain cognition.
3. Hand-written keyword answers belong in seed knowledge/tests, not in the cognitive coordinator.
4. Memory records are evidence, not automatically truth.
5. Contradictory facts must remain representable simultaneously with provenance/confidence.
6. Unknown is a valid result and must not be replaced with an unsupported guess.
7. Benchmarks must test behavior through the public runtime boundary; benchmark code must not monkey-patch production methods.
8. Every new cognitive subsystem must have isolated unit tests plus multi-turn integration scenarios.

## Acceptance gates

### Gate A — conversation
- multi-turn topic continuation
- reference resolution
- explicit correction
- topic restoration
- user fact recall

### Gate B — reasoning
- one-step inference
- multi-step inference
- competing evidence
- contradiction detection
- uncertainty propagation

### Gate C — memory
- working memory
- episodic memory
- semantic memory
- provenance
- persistence/reload

### Gate D — response integrity
- grounded answer
- unknown answer
- verification failure
- repair
- no internal trace leakage

### Gate E — regression
- existing public tests pass
- 100 deterministic scenarios pass without benchmark monkey-patching
- compile/static checks pass

## Migration sequence

1. Freeze master baseline and preserve it as the rollback point.
2. Establish one `CognitiveCore` public entry point.
3. Route conversation runtime through that entry point.
4. Move reference/memory/reasoning/verification into explicit stages.
5. Remove duplicated dialogue wrappers from the active path.
6. Rewrite the benchmark so it exercises the public runtime only.
7. Add 100 multi-turn behavioral scenarios.
8. Compare against the frozen baseline.
9. Only then merge additional cognitive modules.
