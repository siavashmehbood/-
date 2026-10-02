# Rasa Foundation Audit

Examined upstream: RasaHQ/rasa branch 3.6.x, commit 60a3cff9c08183760355b07bd60f5223d8916d6b.
License: Apache-2.0. IRAN implementation is an independent adapter; no upstream source was copied.

## Decision

Reuse the architecture contracts, not the full runtime dependency.

Reusable/adapted:
- NLU result contract: normalized text + intent/confidence + entities.
- Event-sourced conversation history.
- Replayable tracker semantics.
- Slots as bounded explicit conversational state.
- Current-state snapshot boundaries.

Rejected:
- Rasa dialogue policies / TED / RulePolicy as decision owners: they predict next actions and conflict with IRAN's sole CognitiveSystem decision boundary.
- Full DIET runtime dependency in core: TensorFlow, model storage, training graph and model lifecycle are disproportionate for IRAN's local-first core and would duplicate current Persian understanding.
- Rasa response selector/generator as final response owner: IRAN reasoning, planning, verification and evidence governance must remain authoritative.
- Rasa action server as a second tool executor: conflicts with canonical Tool/ComputerUse permission and verification path.

Architecture before:
User -> CognitiveSystem -> CognitivePipeline -> ConversationalUnderstanding/ConversationState -> Memory/Knowledge -> Reasoning -> Plan -> Generate -> Verify -> Learn.

Experimental architecture:
User -> CognitiveSystem -> CognitivePipeline -> ConversationalUnderstanding -> RasaFoundationAdapter (NLU contract + events + slots; no decisions) -> IRAN ConversationState/Memory/Knowledge -> IRAN Reasoning -> IRAN Plan/Tools -> IRAN Generation -> Verification -> Learning.

The adapter is deliberately advisory/state-foundation only. It exposes no decide/predict_action/generate_answer/execute API.
