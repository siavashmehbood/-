# IRAN Cognitive Core Audit

## Audited baseline

Master baseline before this audit: `37796c4898b4ad96272181d7a6961186f37ed348`.

## Findings

### 1. The architecture already has a promising core

`core/cognitive_core.py` already models typed cognitive state with intent, goal, topic, entities, references, evidence, hypotheses, contradictions, unresolved items, plan, and confidence. It also has explicit begin/verify/learn phases.

### 2. The problem is duplication, not absence

The development branch adds a second large family of cognitive modules and a canonical dialogue refactor. The branch is 18 commits ahead of master and changes 27 files, including `core/dialogue.py`, `core/offline_agent.py`, `core/cognitive_controller.py`, `core/cognitive_realizer.py`, `core/unified_pipeline.py`, and several reasoning modules.

### 3. Dialogue needs one owner

The current codebase has multiple concepts that can participate in response generation: dialogue, cognitive core, response engine, offline agent, unified/cognitive pipelines, and runtime routing. The migration must select one owner rather than adding another wrapper.

### 4. Knowledge must be separated from response shortcuts

Hard-coded responses are useful for bootstrap behavior but should not be the long-term representation of knowledge. Facts should live in the knowledge/evidence layer and be retrieved by the cognitive cycle.

### 5. Benchmark quality needs improvement

The development branch's cognitive benchmark includes compatibility/adaptation functions that replace benchmark methods after class definition. The new benchmark must instead call the public runtime and never modify production or benchmark methods to make cases pass.

### 6. Memory must carry provenance

The cognitive state already distinguishes evidence sources and confidence. The next memory contract should make provenance, confidence, timestamp and contradiction status first-class rather than treating recalled text as truth.

## Decision

Do not delete the existing architecture. Do not merge the development branch wholesale. Stabilize the master baseline, create one canonical cognitive entry point, and migrate useful modules behind explicit stage interfaces.

## First implementation milestone

The first milestone is not autonomous behavior. It is reliable Persian multi-turn cognition:

- remember an explicit user fact
- resolve references such as `همون قبلی`
- apply explicit corrections
- retrieve relevant memory/knowledge
- perform symbolic inference
- detect conflicting evidence
- answer unknown when evidence is insufficient
- verify and repair the answer
- persist the resulting state

Only after this milestone passes the behavioral suite should broader autonomy be re-enabled.
