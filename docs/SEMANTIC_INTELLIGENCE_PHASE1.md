# Semantic Intelligence Foundation — Phase 1

## Scope

This phase extends IRAN's existing canonical path. It does not add a second brain.

`IranRuntime -> CognitiveSystem -> CognitivePipeline -> Rasa conversation context -> SemanticIntelligence -> Memory/Knowledge/Reasoning -> Verification -> FinalAnswer`

`CognitiveSystem` remains the sole final decision owner.

## Internal contracts

- `LinguisticAnalysis`: normalized text, tokens, sentence boundaries, POS/morphology placeholders, entities, backend/provenance.
- `SemanticFact`: subject, relation, value, entity type, attributes, source turn/order, confidence, provenance, scope, supersession marker.
- `SemanticQuery`: entity/reference/relation request.
- `EvidenceRecord`: metadata-rich fact evidence with confidence, provenance, score and supersession state.
- `SemanticEvidenceRetriever`: separates storage (IRAN Memory) from filtering/ranking.

Raw history remains evidence/context only. Structured semantic facts are resolved before raw-history recall.

## Framework audit

### Rasa

Already integrated as conversation/NLU/dialogue-state foundation. It keeps tracker/events/slots and never owns final decisions, tool selection, learning approval, answer generation or Computer Use.

### spaCy

spaCy is not a mandatory runtime dependency. If it is already installed locally and `IRAN_NLP_BACKEND=spacy` is selected, IRAN lazily creates a Persian blank pipeline with sentence segmentation and maps its tokens into `LinguisticAnalysis`. Because the blank Persian pipeline has no trained POS/dependency/NER model, those capabilities are explicitly reported unavailable rather than fabricated. The normal offline fallback remains available.

### Stanza

Stanza is not a mandatory runtime dependency. If Stanza and Persian resources are already installed locally and `IRAN_NLP_BACKEND=stanza` is selected, IRAN lazily loads Persian tokenize/MWT/POS/lemma/dependency/NER processors into the same internal `LinguisticAnalysis` contract. Runtime model downloads are disabled. Missing packages/models fail gracefully to the deterministic fallback and record an observable backend error.

### DeepPavlov

DeepPavlov documents NER, slot filling and classification/intent components, but
the published pretrained examples do not establish a sufficiently strong Persian,
offline, dependency-light fit for this runtime. Phase 1 therefore adopts the
requested structured-NLU concepts only: typed entity spans, normalized slots,
intent-separated interpretation, relation/fact representation and entity linking.
No DeepPavlov dialogue manager or answer generator is introduced.

Official sources:
- https://docs.deeppavlov.ai/en/master/features/models/NER.html
- https://docs.deeppavlov.ai/en/0.12.1/features/overview.html

### Haystack

Haystack documents a clear separation between Document Stores and Retrievers.
IRAN keeps its existing Memory/Knowledge storage and implements the same contract
through `SemanticEvidenceRetriever` and metadata-rich `EvidenceRecord` objects.
No Haystack dependency, vector database, embedding service or cloud store is added.

Official sources:
- https://docs.haystack.deepset.ai/docs/3.2/retrievers
- https://docs.haystack.deepset.ai/docs/3.3-unstable/document-store

## Fallback

The default backend preference is `fallback`: deterministic, offline and observable. Optional `spacy` or `stanza` backends are lazy and opt-in. Missing packages/models do not crash the runtime, no runtime downloads occur, and `backend_status()` reports availability/errors while keeping `decision_owner=CognitiveSystem`.

## Semantic behaviour

Explicit factual user statements can produce durable structured facts without requiring "remember this". Questions, commands, speculation and uncertain statements are not persisted as facts.

Coreference uses semantic entity IDs, entity type, recency/Rasa slots, relations and persistent semantic evidence. Multiple entities of the same type can be resolved by ordinal reference or by entity-name linking.

Corrections add a newer fact for the same `subject/relation`; old history remains in the semantic store while retrieval marks older values superseded.

## Anti-echo

Before final acceptance, the semantic anti-echo guard blocks:
- exact question echo,
- near-question echo,
- a previous user question reused as the final answer.

Legitimate factual quoting is preserved. If a structured semantic answer exists it repairs the candidate; otherwise the system abstains instead of returning raw history.

## Observability

Debug/runtime trace includes:
- raw input,
- linguistic analysis,
- entities,
- extracted facts,
- resolved references,
- retrieved semantic evidence,
- answer candidate,
- verification/final answer through the canonical trace.

## Performance

`python -m self.semantic_intelligence_benchmark` records:
- cold runtime start,
- warm turn latency,
- semantic analysis latency,
- semantic evidence retrieval latency.

The benchmark uses generous regression guardrails and no external APIs.
