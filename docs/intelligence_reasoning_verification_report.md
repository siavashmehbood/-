# IRAN — Intelligence / Verification Milestone

## Baseline
- Branch: `cognitive-core-1`
- Previous commit: `c7733c0`
- Runtime remains local/offline and symbolic.

## Changes in this milestone
- Added `SemanticVerifier` as a narrow second verification gate.
- Checks question/answer alignment.
- Detects explicit contradictions with `آفلاین` and `بدون API` constraints.
- Detects repetition of answers already rejected by the user.
- Emits a `semantic_contradiction` event when the gate blocks an answer.
- Integrated the gate into the canonical cognitive pipeline.
- Fixed a latent `re` import defect in `UserModel` that prevented reliable explicit-name extraction.
- Added a memory firewall for explicit name-recall questions so self-correction evidence cannot hijack a memory query.
- Made the 50-turn name-recall assertion data-driven instead of dependent on corrupted/legacy encoded text in the benchmark.
- Added dedicated semantic-verifier regression tests.

## Final verification
- Intelligence benchmark: **200/200 — 1.000**
- 50-turn conversational benchmark: **50/50 — 1.000**
- Full pytest suite: **225 passed**
- `compileall`: passed
- `git diff --check`: passed

## Architectural recommendation
The next milestone should not add more special-case answer rules. The current pipeline has accumulated many compatibility wrappers. Refactor those wrappers into a small number of canonical stages while preserving the 200-check benchmark as a hard regression gate.

After that, improve symbolic reasoning with explicit evidence graphs, contradiction sets, confidence propagation, and multi-step reasoning traces.
