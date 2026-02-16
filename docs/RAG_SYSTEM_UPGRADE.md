# RAG System Upgrade (Query, Retrieval, Safety, Performance)

## Refactored pipeline structure

```text
User Query
  -> Intent Classifier (`classify_intent`)
  -> Semantic Query Expansion (`expand_query_semantically`)
  -> Student Context Injection (`build_student_context`)
  -> Multi-stage Retrieval
      1) Coarse lexical candidate generation (local chunk cache)
      2) Dense vector retrieval (Qdrant + embedding cache)
      3) Re-ranking (lexical + intent/doc-type bonus)
      4) Context compression (`compress_context`)
  -> Strict-grounded prompt assembly
  -> Ollama streaming generation
  -> Citation-enforced response + trace logging
```

## Key implementation points
- **Query processing**: `api/app/services/query_processing.py`
- **Chunk strategy + segmentation**: `optimize_chunk_params`, `infer_doc_type` in `api/app/services/rag.py`
- **Multi-stage retrieval + re-rank**: `retrieve(...)` in `api/app/services/rag.py`
- **Context compression**: `compress_context(...)` in `api/app/services/rag.py`
- **Embedding cache (TTL LRU)**: `api/app/services/ollama.py`
- **Strict grounding/citation enforcement**: `api/app/routers/chat.py`

## Prompt template (strict grounding)
```text
[SYSTEM]
Tu es un co-créateur pédagogique EPS.
Mode ancrage strict:
- N'affirme rien sans preuve dans les extraits.
- Si la preuve est insuffisante, réponds "Sources insuffisantes".
- Cite chaque affirmation clé au format [doc:ID p.PAGE].

[USER]
Question: {user_query}
Contexte étudiant: {student_context}
Intent détecté: {intent}
Requêtes d'expansion: {expanded_queries}
Sources PDF compressées:
{compressed_sources}
```

## Example Python snippet (orchestration)
```python
intent = classify_intent(query, mode)
expanded = expand_query_semantically(query, intent)
student_ctx = build_student_context(student_level, confidence, pseudo=user_name)

hits = await retrieve(
    query,
    doc_ids=collection_ids,
    top_k=10,
    expanded_queries=expanded,
    intent=intent,
    metadata_filters={"doc_types": ["practice"]},
)
compressed = compress_context(hits, max_chars=1600)
```

## Example safety policy
- `strict_grounding=True` + `use_rag=True` + no citations => fallback output:
  - `Sources insuffisantes pour répondre de manière ancrée sur les PDF sélectionnés.`

## Performance notes
- Embedding calls are cached by `(model, text)` with TTL and LRU eviction.
- Retrieval uses lazy strategy:
  - skip retrieval work if `use_rag=False`
  - retrieval only when selected docs or metadata filters are present.
- Streaming remains SSE token-by-token from Ollama.
