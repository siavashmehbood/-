# Validation record

Baseline: `5476939e50852f550d3cd67acc4f1e8319b9612e`.
The same isolated runtime evaluation was run against the baseline snapshot and the revised checkout. No production user state was used.

| Measure | Baseline | Revised |
| --- | ---: | ---: |
| Behavioral runtime scenarios | 8 / 15 | 15 / 15 |
| Existing baseline pytest suite | 303 passed | preserved, no removed/relaxed tests |
| Full revised pytest suite | — | 419 passed |
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

Runtime ownership is tested with two objects, two subprocesses, separate roots, failed initialization, abrupt exit and attempted use after close. Only one runtime may own a data directory.

Curriculum follow-up: repeated or distinct claim retrievals are recorded as retrieval evidence without advancing a stage. Only explicit evaluation assessments advance curriculum. This separation is tested both on persisted goals and through approved-knowledge reuse in the runtime.


## Evidence conflict checkpoint

Against checkpoint `59bdadb`, the expanded identical runtime suite improves from
15/16 to 16/16: approved competing capital facts now cause abstention, not a
confident answer. Existing 15 scenarios remain passing. Full pytest: 392 passed;
legacy unittest: 234 passed. Conflict abstention survives restart.

Verification now reports SUPPORTED, REFUTED, NOT_ENOUGH_INFO or CONFLICTING plus
source identifiers. A mention in an unrelated clause cannot support a fact, and
negating a known fact is rejected. UNKNOWN is not logged as a verified answer.
Both short and repaired long answers are checked before memory commit.

An ordinary competing observation retains unresolved evidence; only an explicit
correction marks prior values superseded. Old contradiction markers alone are
not assumed to prove resolution. Correction back to an earlier value survives
restart without deleting historical facts.

Design inspiration: [FEVER (Thorne et al., 2018)](https://arxiv.org/abs/1803.05355)
separates supported/refuted/insufficient-evidence judgments. IRAN adds a local
conflict state; it does not implement or claim FEVER benchmark performance.
These checks cover narrow structured relations, not unrestricted natural-language
entailment or arbitrary factual truth. Automated reviewer fixtures are not live
external-service validation.


## Gated correction checkpoint

`knowledge.contradict` proposals previously reached human review but failed with
`unsupported_proposal_kind`. The existing approval dispatcher now applies them
inside its existing rollback checkpoint and gate bypass, after reviewer and
human approval. No alternate learning pipeline was added.

The identical expanded runtime suite improves from 16/17 at `c4181cc` to 17/17.
Full pytest: 394 passed; unittest: 234 passed. Additional integration tests cover
unapproved/reviewer-only correction remaining unapplied, correction of competing
facts, repeated approval rejection, zero artificial XP, restart retrieval, and
interruption after mutation followed by rollback and successful retry.


## Learned-store recovery checkpoint

Before this change, 8 new corruption regressions failed: graph/skills/procedures/
compositions/trusted-source state could be treated as empty, and three stores
ignored a valid backup. A further regression reproduced approval failing after
graph backup recovery because the checkpoint reread the damaged primary.

Knowledge, procedures, skills, compositions and trusted-source bundles now use
critical-state loading. Procedures and skills use the shared atomic writer with
backups. Unrecoverable JSON fails closed without overwriting either copy.
Approval snapshots use the same recovered state as runtime stores.

Full pytest: 404 passed; unittest: 234 passed. Identical runtime evaluation:
17/18 at `56aef7e` → 18/18, including recovery followed by new approved knowledge
while retaining the old fact. This is not a claim of complete corruption-proof
storage: arbitrary semantic/schema corruption and physical disk loss remain
outside these tests.


## Reviewer-state recovery checkpoint

Four regressions reproduced queue replacement after corruption, false zero GUI
counts despite a valid backup, worker cooldown bypass and provider cooldown
bypass. Queue transactions/readers and cooldown readers now use critical loading.
Unreadable provider health reports ERROR and sends no request; unreadable worker
state preserves the candidate in WAITING_FOR_REVIEWER. Valid backups retain
rate-limit deadlines. Both damaged copies are left intact for recovery.

An actual Qt offscreen regression also checks visible state errors, a working
chat send button after review-queue failure, and an error dialog instead of an
uncaught review-status exception. No Windows desktop interaction is claimed.
Full pytest: 411 passed; unittest: 234 passed. The expanded identical runtime
suite improves from 18/19 at `dafd21e` to 19/19.


## Learning control-state recovery

Six new regressions failed on `3d12748` and pass after the change: curriculum,
ingestion, internet-learning and capability state no longer silently reset on
corruption; ingestion deduplication recovers from backup; missing-primary goal
state also recovers from backup. These stores reuse the existing critical loader
and atomic writer. Full pytest: 417 passed; unittest: 234 passed; behavioral
runtime evaluation: 19/19. No new provider credentials or network requests.


## Corroborating provenance

A regression reproduced two approved sources collapsing into the first source
on a deduplicated fact. The graph now retains one source observation per source,
with first/last local recording times and reported confidence. These are local
recording timestamps, not invented retrieval timestamps. Existing source fields
are retained for compatibility; legacy observations migrate lazily on update.
Answer evidence traces expose all recorded source identifiers. Repeating a
source adds neither another observation nor XP nor confidence merely by repetition.
This does not establish that two sources are independent or factually correct.

Full pytest: 419 passed; unittest: 234 passed. Same runtime suite: 19/20 before,
20/20 after. Approved corroboration remains available after restart.
