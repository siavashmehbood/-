# Validation record

Baseline: `5476939e50852f550d3cd67acc4f1e8319b9612e`.
The same isolated runtime evaluation was run against the baseline snapshot and the revised checkout. No production user state was used.

| Measure | Baseline | Revised |
| --- | ---: | ---: |
| Behavioral runtime scenarios | 8 / 15 | 15 / 15 |
| Existing baseline pytest suite | 303 passed | preserved, no removed/relaxed tests |
| Full revised pytest suite | — | 452 passed |
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


## Restricted experiment boundary

The old substring filter allowed importing builtins and writing outside the
experiment directory through an alias. Six rejection regressions reproduced the
bypass (using disposable test files only). The production tool now validates a
small AST subset, excludes imports/reflection/classes, limits available builtins,
and executes inside a fresh child with memory/CPU/file-size limits. Output uses
bounded files rather than unbounded parent-memory pipes. Timeout is a failed
experiment, not a successful action.

12 focused tests pass, including actual execution of every existing capability
template and bounded failures for infinite loops, excessive output and memory.
Full pytest: 431 passed; legacy unittest: 234 passed. Identical runtime suite:
20/21 at `b26bca9` → 21/21, including the actual ActionExecutor boundary.

**Platform limitation:** execution requires resource limits exposed by Python's
Unix `resource` module. Unsupported platforms, including native Windows, return
`sandbox_resource_limits_unavailable` without starting code. Core chat/review
remain independent. This is a restricted deterministic experiment tool, not an
OS container or a security guarantee for arbitrary Python/native extensions.

Design references: Python's [AST documentation](https://docs.python.org/3/library/ast.html)
and [resource limits](https://docs.python.org/3/library/resource.html). No external
code was copied. AST restriction and process limits provide complementary checks;
Python isolated mode alone does not prevent filesystem/network operations.


## Capability evidence validity

Three new regressions reproduced unrelated smoke tests promoting domain skills,
missing executable artifacts, and a broken implementation passing transfer
because transfer executed unrelated hard-coded expressions. Generic tests now
report diagnostic_only, never claim verification or a promotable domain skill.
The currently supported artifact is local integer addition, retained as executable
code and checked on held-out negative/zero inputs. Its goals and description
refer to that contract, not the source topic or unverified source claim.

A real runtime integration test executes experiments, requires both reviews,
restarts, reloads the approved artifact and executes it on a new input. A constant
implementation overfitted to the training example fails transfer. No XP is minted.
Existing tests were not removed or weakened. Full pytest: 435 passed; unittest:
234 passed. Same runtime evaluation: 21/22 before, 22/22 after.

This does not demonstrate general skill acquisition or measured improvement over
a prior model. Only the addition contract has a promotion/held-out contract here;
other existing templates are diagnostics. Historical saved skills are not deleted
or retroactively declared validated by the new checks.


## Internet permission recovery

Unlike learned data, permission cannot safely be restored from an older backup:
it may precede revocation. Six new tests reproduced re-enabling from strings or
numbers, stale enabled backups after a missing/corrupt OFF primary, and an enable
write failure leaving network allowed in memory. Only a valid boolean in the
current primary now authorizes restart access; explicit enable repairs state.
Write failures leave this process offline and surface the error. A failed disable
write cannot promise persistence across restart; disk errors must be resolved.
The GUI catches write errors, displays OFF and starts no reviewer job.

Full pytest: 446 passed, including the Qt error path; unittest: 234 passed.
Identical runtime suite: 22/23 before, 23/23 after. These tests do not call a live
provider or assume credentials/quota availability.


## Grounded memory consolidation

Four new failures exposed legacy wrapper defects: the role filter inspected
numeric similarity scores rather than roles, discarded relevant memories, then
an unconditional fallback accepted unrelated recent text and assistant output.
The synthesizer now has one implementation for fact/memory selection. Roles are
filtered before scoring; user questions, telemetry and generated assistant answers
cannot ground factual responses. Unrelated recent text no longer bypasses ranking.
Relevant explicit user statements remain attributed to memory, not external truth.
125 lines of wrapper/parallel implementation were removed while preserving all
prior tests. Superseded facts are excluded from candidate generation.

Full pytest: 452 passed; unittest: 234 passed. Identical runtime suite: 23/24
before, 24/24 after. New runtime tests check assistant self-confirmation across
restart and 50 conversation turns with repeated identity corrections and topic
changes exceeding the working-memory window, followed by successful restart recall.


## Structured evidence subject binding

A matching predicate and object previously authorized a statement about a different
subject. Verification now requires the evidence subject in the same clause as
its predicate and object, while retaining short-answer and profile handling.
Regression tests cover a wrong subject, a subject mentioned in an unrelated clause,
and runtime rejection before the unsupported answer enters memory.
This is bounded structured consistency checking, not general factual entailment.

Full pytest: 455 passed; unittest: 234 passed. The identical runtime evaluation
suite passes 24/25 on baseline 2e21f12 and 25/25 after the correction.
Live external services remain untested.


## Final answer constraints

Short-route persistence and the final post-repair check now receive remembered
constraints and rejected answers, matching the earlier semantic check. Two
runtime regressions reproduced short-route acceptance of an API recommendation
under stored offline/no-API constraints. Both now reject before memory commit.
The existing keyword-based constraint checker remains limited; this change closes
a routing omission, not general semantic instruction following.

Full pytest: 457 passed; unittest: 234 passed. Identical runtime evaluation:
25/26 on 7985d57, 26/26 after. Qt tests run with the offscreen platform.


## Numeric evidence fidelity

Verifier tokenization discarded single digits and signs and split decimals into
unordered fragments. Three new tests reproduced valid numeric answers being
rejected and wrong decimal/sign values being accepted. Numeric tokens now retain
single digits, decimal order and signs; Persian/Arabic digits, decimal separator
and Unicode minus normalize to the same representation as ASCII.
A gated-learning runtime test restarts the runtime, recalls signed numeric evidence,
and rejects a changed sign before memory commit. Reviewer approval in this test
is an explicit fixture, not a live external service. This does not implement
unit conversion, scientific notation or general arithmetic equivalence.

Full pytest: 461 passed; unittest: 234 passed. Identical runtime evaluation:
26/27 on 4509b88, 27/27 after. Qt tests run offscreen.


## Structural learning-queue recovery

The approval store previously checked only JSON syntax and the top-level list.
Malformed rows could hide decisions or crash later queue reads even when a valid
backup existed. The gate now validates row identity, kind, payload, decision state
and unique proposal IDs on initial load and every locked reload. Unrecoverable
state raises StateCorruptionError without replacing the file. A validated backup
is restored before later saves can overwrite it with a structurally invalid
primary. Other stores retain their existing loader behavior unless they supply
a validator; this is not a claim of comprehensive schema validation everywhere.

Six regressions cover recovery, preservation of approved history, malformed
states, unrecoverable state and reloads. Full pytest: 467 passed; unittest: 234
passed. Identical runtime evaluation: 27/28 on 9b0bfa3, 28/28 after, including
restart recovery, duplicate prevention and no XP creation during recovery.


## Credential-free external access policy

The project now defaults to external_access.credential_free_only=true. The
runtime passes this policy independently of reviewers.local.json; enabling a
legacy adapter locally cannot override it. Keyed or undeclared adapters are
unavailable with credentials_disallowed, visible in Persian in the GUI. No new
anonymous reviewer is claimed. A fixture explicitly declaring anonymous access
tests extensibility only, not a live service. Existing free-tier adapters remain
available to explicit configurations outside the credential-free policy.

Full pytest: 470 passed; unittest: 234 passed. Identical runtime evaluation:
28/29 on c3d34ad, 29/29 after. Candidates remain pending and hidden from human
review when no eligible external reviewer exists.

Live anonymous retrieval of https://docs.python.org/3/tutorial/ through the
production fetch method was attempted and BLOCKED by DNS resolution in this
execution environment. No credentials were supplied, and no live connection
success is claimed. Public-source retrieval is not external AI approval.

Research: official Pollinations API docs currently require a key for generation:
https://github.com/pollinations/pollinations/blob/main/APIDOCS.md
MediaWiki documents public content retrieval separately from authentication:
https://www.mediawiki.org/wiki/API:REST_API
Neither source establishes an unlimited, anonymous AI reviewer for IRAN.


## Provider health structure

Provider health now rejects non-object rows and nonnumeric, boolean, negative or
non-finite cooldown/success timestamps. Previously these values could crash health
readers or authorize a request by making the cooldown comparison false. Structural
corruption is visible as provider_state_corrupt and keeps review waiting without
sending a request. This check deliberately does not reset the corrupt health file.

Full pytest: 475 passed; unittest: 234 passed. Identical runtime evaluation:
29/30 on 24fe6a5, 30/30 after. These are local failure-injection tests; no live
external reviewer success is claimed.
