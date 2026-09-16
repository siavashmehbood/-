# Conversation & Context subsystem

**Purpose** — Maintain enough context across turns that a short follow-up such as
«چطور کار می‌کنه؟» is understood relative to what was just discussed, without any
language model.

**Input** — Raw Persian user text per turn, plus the parsed analysis produced by the
language layer (`goal`, `entities`, `question_units`).

**Output** — A response string for the user, plus a persisted conversation state used
by later turns.

**Dependencies** — Standard library only. `core/conversation_state.py`,
`core/dialogue.py`, `core/chat_upgrade.py`, `core/cognitive_fabric.py`.

## Canonical state model

`core/dialogue.py::ConversationState` is the state that the runtime actually uses.
`LocalDialogueEngine` holds one instance and persists it to
`data/conversation_state.json` on every turn.

Fields that matter in practice:

| Field | Role |
|---|---|
| `turns` | Monotonic turn counter |
| `current_topic` | What the conversation is currently about |
| `topic_stack` | Previous topics, capped at 12, for «موضوع قبلی» |
| `active_goal` | The user's standing goal |
| `references` | Resolved anaphora per turn |
| `corrections` | Turns where the user redirected the system |
| `unresolved_questions` | Topics that could not be answered |
| `last_answer_type` | How the previous answer was produced |

## Known duplication (recorded, deliberately not merged yet)

A second state class exists at `core/conversation_state.py::ConversationState`, with a
different field set (`topic`, `referent`, `unresolved`). It is used by `core/agent.py`
and covered by `tests/test_conversation_state.py` (21 tests). The runtime uses the
`core/dialogue.py` class.

These two are **not** interchangeable: the dialogue class is turn-oriented and tracks a
topic stack, the other is a light summary record. Merging them would be a behaviour
change across two live call paths, so this audit records the overlap rather than
forcing a merge. What *was* unified is the genuinely identical part — see below.

## Normalization is now single-sourced

`clean()` and `substantive()` existed as byte-identical definitions in both
`core/dialogue.py` and `core/conversation_state.py`. A normalization fix applied to one
module would silently miss the other. `core/dialogue.py` now imports them from
`core/conversation_state.py`, so there is exactly one definition of Persian
normalization (`ي→ی`, `ك→ک`, whitespace collapse).

`bare()` and `words()` remain local to `core/dialogue.py` because they are not
duplicated anywhere.

## Tests

| Suite | Covers |
|---|---|
| `tests/test_conversation_state.py` | 21 tests on the summary state model |
| `tests/test_dialogue_smoke.py` | Reference phrases, correction, topic stack, compound split |
| `tests/test_dialogue_runtime.py` | End-to-end follow-up, correction, topic restore, persistence across restart |
| `tests/test_conversation_output.py` | User-facing output, honest UNKNOWN |
| `tests/test_answer_hygiene.py` | No internal pipeline wording reaches the user |
| `benchmarks/persian_conversation_benchmark.py` | 100 scenarios, 10 categories |

## Answer hygiene rule

The project requires that internal analysis never reaches the user. Two canonical sites
violated it by narrating the pipeline inside the reply:

1. `AnswerRepair.repair` produced «بخش باقی‌مانده سؤال: «…». برای این بخش شواهد کافی
   ندارم.» — quoting the question as an internal unit and announcing its own evidence
   policy.
2. A chat layer appended the last line of the rejected answer to a follow-up, which was
   frequently that same notice.

Both are fixed, and `tests/test_answer_hygiene.py` asserts no pipeline vocabulary
appears in any user-visible answer, including every benchmark answer. The guard was
mutation-tested: restoring the old wording fails the suite.
