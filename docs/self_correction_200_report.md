# IRAN — Self-Correction / Intelligence 200 Report

## Scope
- Branch: `cognitive-core-1`
- Baseline: `d4e6ffd feat: strengthen persistent multi-turn chat memory`
- Runtime: local / offline symbolic
- Network tools: disabled in `config.json`

## Changes
- Added persistent `SelfCorrectionEngine`.
- Negative feedback is stored as rejected-answer evidence.
- Explicit corrections are linked to the question/answer they corrected.
- Future matching uses question similarity, not generic correction-text similarity.
- Rejected answers are guarded against repetition.
- Added deterministic topic/reference repair at the canonical pipeline boundary.
- Added explicit constraint recall for `آفلاین` and `بدون API`.
- Added high-confidence local realization for Django, Python learning and Episodic/Semantic comparison.
- Added 200-check intelligence benchmark and self-correction unit tests.

## Final verification
- 200/200 intelligence checks passed.
- 50/50 conversational memory harness passed.
- 222 pytest tests passed.
- `compileall` passed.
- `git diff --check` passed.

## Behavioral target
The system now has a complete local loop for conversational correction:
`answer -> explicit feedback/correction -> durable lesson -> future retrieval -> changed behavior`.

## Recommendation
Next work should focus on simplifying the accumulated compatibility wrappers in
`core/cognitive_pipeline.py` into fewer canonical components, while preserving the
200-check benchmark as a regression gate. The next milestone should improve
reasoning quality rather than merely adding more memory fields.
