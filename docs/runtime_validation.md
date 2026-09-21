# Validation record

Baseline: `5476939e50852f550d3cd67acc4f1e8319b9612e`.
The same isolated runtime evaluation was run against the baseline snapshot and the revised checkout. No production user state was used.

| Measure | Baseline | Revised |
| --- | ---: | ---: |
| Behavioral runtime scenarios | 8 / 15 | 15 / 15 |
| Existing baseline pytest suite | 303 passed | preserved, no removed/relaxed tests |
| Full revised pytest suite | — | 375 passed |
| Legacy unittest discovery | 234 passed | 234 passed |

The 15 scenarios cover topic switching, verified action recovery, multi-turn identity recall, correction, reference resolution, unknown handling, restart memory, external then human approval, hidden candidates, feedback without XP, candidate deduplication, untrusted review metadata, source conflict detection, offline/provider fallback and approved knowledge reuse credited once. See `runtime_evaluation.json` for individual outcomes and `evaluation/runtime_suite.py` to reproduce. This is a regression suite, not a percentage measure of general intelligence.

Additional pytest regressions execute:

- Provider unavailability, rate limits, malformed responses, bounded retries, persistent cooldown, invalid configuration and remaining request budget.
- Queue mutation during review; Internet OFF sends no request; restart preserves the pending candidate; Internet ON resumes; duplicate processing/learning is avoided.
- Human approval failure after SQLite mutation, after gate update and during review-status update. One test terminates a subprocess with `os._exit` and verifies rollback and safe retry after restart.
- Upgrade of legacy episode-based XP credits: historical balance and ledger retained, repeated effect receives no new credit. Role statements do not overwrite a recorded name.
- Critical JSON primary corruption with valid backup, and both copies unreadable. Existing approval/XP state is not silently reset.
- Actual PySide6 offscreen windows with a Qt timer during a slow reviewer and during a blocked human-decision operation. Heartbeats continue and worker completion permits safe close.
- Actual claim retrieval after learning, with one durable XP credit across repeated use and restart.

Real CLI startup and commands are exercised separately. GUI testing here is Linux offscreen event-loop execution; interaction on the user's Windows desktop was not verified.

## Not established / blocked

- **BLOCKED:** live OpenRouter/Gemini/Groq/Cerebras requests without configured keys, current free-access confirmation, model availability and account quota. Fixture success is not live-service success.
- **Not established:** general intelligence, arbitrary-domain fact checking, full confidence calibration or curriculum mastery. Current verification and source conflict detection are narrow deterministic checks.
- **Ownership constraint:** one runtime per data directory. Multi-process concurrent writers to learned stores are not supported.
- Existing legacy pipeline wrappers remain technical debt. The report does not declare a completed architecture rewrite.

Verification follow-up: unrelated informational answers are rejected, relevant stored facts can support short answers, and the final consistency check retains existing REPAIR/CLARIFY/UNKNOWN status and reasons. These checks do not establish arbitrary factual truth.
