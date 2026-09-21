# Runtime architecture and remaining boundaries

The active composition root is `runtime/app.py:IranRuntime`. CLI `main.py` and GUI `gui.py:ChatWindow` share it. `providers/iran.py` generates local answers. The names `ChatGPTReviewWorker` and `chatgpt_reviews.json` are retained for data/import compatibility, but the worker now delegates to `ProviderManager`; they do not imply an OpenAI dependency.

## Data and approval ownership

| Data | Owner | Durable storage |
| --- | --- | --- |
| Conversation, explicit personal facts, semantic facts, lessons | Memory | configured SQLite database |
| Claims and facts | KnowledgeGraph | `data/knowledge.json` |
| Source evidence and review provenance | TrustedKnowledge bootstrap | `data/trusted_knowledge.json` |
| Candidate identity and human decision | LearningGate | `data/learning_proposals.json` |
| External review, provider/model, human queue state | Review worker / MCP bridge | `data/chatgpt_reviews.json` |
| Provider cooldown and last outcome | ProviderManager | `data/reviewer_health.json` |
| Experiences, learned rules and lessons | LearningEngine | `data/experiences.json`, `learned_rules.json`, `learned_lessons.json` |
| Applied effects, credit identities and confidence evidence | EffectLearningLoop | `data/effect_learning.json` |
| Curriculum goals and distinct assessments | SelfDirectedLearning | `data/learning_goals.json` |

The review queue uses short locked read/modify/write transactions. No queue lock is held over network I/O. The worker serializes processing separately and merges results into the latest queue; concurrent new candidates are not discarded. A rejection while a request is in flight is not resurrected by its result.

Human approval checks the persisted external decision, then creates an approval checkpoint. A runtime mutation lock serializes chat, maintenance and approvals. The checkpoint covers learned stores, SQLite and only the affected proposal/review rows. On an interrupted application, mutation is blocked until restart; startup rolls back before opening the learned stores. Unrelated queued candidates survive. A committed checkpoint is only cleaned up. Files outside learned stores (for example the append-only diagnostic event log) are not rolled back; an event by itself is not approval authority. This is a single-runtime ownership model, not a distributed transaction protocol. Do not run two IRAN runtimes against one data directory.

JSON updates use replacement plus fsync; critical approval/experience/effect state loads a valid backup or raises a corruption error. Backups do not replace an external backup policy. Python callers with write access to the data directory or internal `gate.bypass()` are trusted code; these are not a security boundary against arbitrary local code execution.

## Provider and source separation

Providers assess candidates; source adapters retrieve evidence. Source text and reviewer prompts are treated as untrusted content. Only configured sources or explicit `/learnweb` URLs are retrieved. `learning_tick` selects an existing gap/curriculum goal with matching sources and a bounded attempt count. A returned reviewer decision cannot itself add a new fact.

The four reviewer adapters share strict response parsing, fixed trusted endpoint hosts, no redirects, bounded response size, request timeout, bounded attempts and durable cooldown. Free-access confirmation is model-specific and expires. The local policy cannot independently inspect account billing. `AVAILABLE` is computed configuration eligibility; `last_success` is the recorded successful response time. No keys or model quotas were available in this verification session, so real provider integration remains unverified.

Internet OFF prevents new requests; it cannot retroactively cancel an already submitted HTTP request. Source URL validation rejects private/local address destinations and checks redirects. DNS is checked before opening; DNS rebinding is not pinned at the socket layer. Source cross-checking uses lexical, numeric and negation heuristics, not a universal truth detector. Domain independence uses a conservative suffix approximation, not a maintained public-suffix database.

## Reasoning, verification and effect

`CognitiveSystem` owns a single `CognitivePipeline`. Memory/context retrieval, reasoning/planning, grounded synthesis and semantic checking remain independently testable components. Early deterministic answers now run the consistency verifier before persistence and all natural-language turns pass the final checker. Consistency PASS is not evidence of factual truth. Unknown responses retain low confidence and create deduplicated learning gaps.

Explicit identity/preference statements from the user are local conversation facts and are usable immediately. Internet and inferred learned claims need external and human approval. Approved knowledge reuse is measured by matching an approved claim to the actual emitted answer. This supports observing exact retrieval and credit deduplication; it does not establish causality or a general improvement in reasoning. Curriculum progression records distinct verified assessments; broad domain mastery still needs richer held-out tasks.

## Legacy audit

- One `ChatWindow` is the GUI. No `iran_gui.pyw` launcher exists in this checkout.
- `CognitivePipeline.run` still contains successive `_v*` compatibility wrappers, and several other modules retain historical monkey-patches. These share the runtime and final verifier, but remain refactoring debt; they were not deleted just to reduce file count.
- `Orchestrator`, `AdvancedCognitiveCore` and kernel compatibility entry points are bound through `CognitiveSystem.bind_legacy_adapters`. Task execution and explicit CLI commands retain their adapters.
- `OpenRouterProvider` and `RemoteProvider` no longer contain independent HTTP clients. Legacy imports use local answers and the same reviewer manager.
- The MCP review bridge writes the same external-review queue and does not apply learning. Its callers are trusted external review operators; human approval remains separate.
- Earlier architecture/audit documents describe historical versions. This document and the current runtime evaluation are the current tested contract.

Next engineering work should target wrapper consolidation with held-out language regressions, stronger provenance/conflict models and confidence calibration. It should not reintroduce a parallel learning pipeline or automatic approval.
