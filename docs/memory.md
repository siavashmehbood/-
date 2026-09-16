# Memory & Knowledge Graph subsystem

**Purpose** — Keep durable, inspectable local memory across sessions: what happened
(episodic), what is true (semantic), how to do things (procedural), and how concepts
relate (graph).

**Input** — Text, facts, lessons and outcomes produced during conversation and
autonomy.

**Output** — Retrievable rows and ranked results for the answer layer.

**Dependencies** — Standard library only (`sqlite3`, `json`). No external store, no
embedding service, no network.

## Storage

| Tier | Implementation | Backing store |
|---|---|---|
| Episodic / short-term | `memory/store.py::Memory` (`memories` table) | SQLite at `data/iran.db` |
| Semantic facts | `Memory.add_semantic_fact` (`semantic_facts` table) | SQLite |
| Procedural lessons | `Memory.add_lesson` (`lessons` table) | SQLite |
| Time-scoped recall | `memory/episodic.py::EpisodicMemory` | SQLite via `Memory` |
| Semantic consolidation | `memory/semantic.py::SemanticMemory` | SQLite via `Memory` |
| Knowledge graph | `knowledge/knowledge_graph.py::KnowledgeGraph` | JSON (`atomic_write_json`) |
| Procedures | `learning/procedural_memory.py`, `learning/skill_system.py` | JSON |

Writes are atomic (`persistence.atomic_write_json`) with backup-based load, so a crash
during a write does not truncate the graph.

## Lifecycle operations

The mission requires memory to be storable, retrievable, updatable, deletable,
validatable and traceable. Retrieval and storage already existed. Added:

| Operation | API | Notes |
|---|---|---|
| Store | `Memory.add`, `add_semantic_fact`, `add_lesson` | Existing |
| Retrieve | `Memory.search`, `working_context`, `semantic_search`, `lesson_search` | Existing |
| Trace | `Memory.get(memory_id)` | New — full row for one id |
| Update | `Memory.update(memory_id, ...)` | New — touches only named fields |
| Delete | `Memory.forget(memory_id=None, kind=None, content=None)` | New — requires a criterion |
| Validate | `Memory.validate()` | New — reports, never repairs |

Two deliberate safety choices:

- `forget()` raises `ValueError` when called with no criterion. This is the one
  destructive operation on durable memory, so it must name what it removes rather than
  defaulting to everything.
- `validate()` never repairs. A validator that fixes corruption silently hides it;
  this one describes the problem and lets the caller decide.

`update()` clamps `importance` and `confidence` to `[0, 1]` and rejects empty content,
so a caller cannot write a value the ranking code would later misread.

## Knowledge graph

`KnowledgeGraph` stores facts as `{subject, predicate, object, confidence, source,
updated_at}`, with `contradicted_by` attached when a competing object is recorded.

Existing capabilities: `add_fact`, `contradict`, `query`, `related`, `infer` (bounded
multi-hop with confidence propagation), `contradictions`, `best_fact`, `add_node`,
`add_edge`, `neighbors`, `graph_query`.

Added:

- `trace(subject, predicate=None, depth=3)` — returns the provenance chain. `infer`
  reported an inferred confidence but not the path that produced it, so a conclusion
  could not answer "which facts produced this?". `trace` records the ordered path and
  the confidence actually propagated at each hop.
- `validate()` — checks the invariants the traversal code depends on: required fields
  present, confidence usable as a weight, and `contradicted_by` pointing at a real
  competing object rather than itself.

Traversal is bounded by `depth` and a `seen` set, so a cyclic graph terminates.

## Tests

| Suite | Tests | Covers |
|---|---|---|
| `tests/test_memory_lifecycle.py` | 15 | Store, retrieve, trace, update, delete, validate, reopen |
| `tests/test_knowledge_graph_contracts.py` | 13 | Trace, contradiction, validation, bounded traversal, reopen |
| `tests/test_episodic_memory.py` | 2 | Time-scoped retrieval |
| `tests/test_persistence_recovery.py` | — | Knowledge and goals survive restart |

## Known limits

- `Memory.search` scores lexically (token overlap, phrase match, recency, usage,
  fixed-weight confidence). There are no embeddings by design, so paraphrase recall
  depends on token overlap. Improving this is a ranking change, not a storage change.
- The graph is a flat fact list rather than an indexed adjacency structure. Traversal is
  O(facts) per hop. Correctness is fine at the current scale; indexing is a performance
  task, deferred until measured.
