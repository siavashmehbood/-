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

No DeepPavlov dependency/model is installed. Phase 1 adopts its structured-NLU concepts only: entity extraction, relation/fact representation, entity linking and contextual query interpretation. It is not used as a dialogue manager or answer generator.

### Haystack

No Haystack dependency, vector database or cloud service is added. Its requested architecture concepts are implemented internally: evidence records, metadata-rich retrieval, filtering/ranking, provenance, duplicate/supersession handling, and storage/retrieval separation.

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
