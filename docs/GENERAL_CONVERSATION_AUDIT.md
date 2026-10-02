# General Conversation Audit

Baseline audited at `a05a224309ce9b116f9d9989f8a2398135fd32b2`.

## Root causes

IRAN already had strong building blocks: persistent ConversationState, ContextTracker,
ReferenceIntelligence, memory/knowledge retrieval, reasoning/planning, verification and
learning governance. The weakness was primarily integration and generalization:

1. The canonical pipeline contained many early phrase-specific returns. Some ordinary
   utterances therefore exited before retrieval, reasoning, answer planning and verification.
2. QuestionAnalyzer was question-centric; non-question dialogue acts had no shared semantic
   representation.
3. Follow-ups were recognized, but response intent (social, simplify, example, meta,
   continuation, return-to-topic) was not first-class in AnswerPlanner.
4. Local generation mixed compositional state-aware realization with hard-coded factual
   branches, making unseen conversational paraphrases brittle.
5. Reference/topic persistence was stronger than surface generation, so the system could
   remember context without consistently expressing it naturally.

## Remediation architecture

`ConversationalUnderstanding` is a mechanics/meaning layer beneath the existing canonical
brain. It emits `UtteranceMeaning` (normalized text, language, dialogue act, intent,
entities, references, topic, requested action/answer type, ambiguity/confidence, temporal
signals and incompleteness). It never produces a user answer and owns no memory/planner.

The canonical route remains:

`IranRuntime -> CognitiveSystem -> CognitivePipeline -> UtteranceMeaning -> ConversationState
-> reference/memory/knowledge -> reasoning -> AnswerPlanner -> local compositional realization
-> verification/repair -> state/memory/learning evidence`.

No external LLM is required. User corrections/failures continue through existing Cognitive
Growth / reviewer / human / LearningGate governance; this layer cannot approve learning.
