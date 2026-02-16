# ChatEPS_PROTO — Phase 1 Architecture Audit

## Scope
This audit maps the current architecture and pinpoints bottlenecks and structural risks before deeper refactors.

---

## 1) Current architecture map

### Runtime topology (current)

```text
[Browser]
   |
   | HTTP
   v
[FastAPI app]
   |- Serves static UI (api/app/static/index.html)
   |- Routers:
   |   - /chat       (conversation CRUD + SSE generation)
   |   - /library    (PDF upload + async ingestion)
   |   - /artifacts  (artefact CRUD/versioning)
   |   - /dashboard  (progress/traces)
   |   - /system     (health)
   |
   |- SQLAlchemy ORM -> SQLite (users, docs, convs, messages, traces, artifacts)
   |- RAG service
   |   - pypdf extract -> chunk_text
   |   - embeddings via Ollama (/api/embeddings fallback /api/embed)
   |   - vector upsert/search in Qdrant
   |   - local JSON chunk cache fallback lexical retrieval
   |
   \- Ollama chat streaming (/api/chat)
```

### Data-flow map
1. **Chat streaming**: UI -> `/chat/conversations/{id}/stream` -> store user message -> optional retrieval -> Ollama SSE -> store assistant message at stream end.
2. **PDF ingestion**: UI upload -> `/library/upload` -> DB status=processing -> background task ingestion -> chunk cache + optional vectors -> status ready/failed.
3. **Conversation ownership**: pseudo identity (`X-Pseudo`) -> `users` row autoprovision + trace events used to derive visible conversations.

---

## 2) Bottlenecks and performance pain points

### A. Retrieval latency and wasted work
- `embed_texts()` performs sequential per-text embedding calls, increasing ingestion latency for large PDFs.
- Query-time retrieval always attempts vector path first, even when ingestion was lexical-only fallback, adding avoidable timeout/exception overhead.
- No query result caching (same prompt + same doc set recomputes embeddings/retrieval each turn).

### B. Over-fetching and repeated DB scans
- Conversation list resolves ownership by scanning all `trace_events` with `conversation_create`, then querying conversations with `IN (...)`.
- Rename/delete perform ownership checks by re-reading all creation events each call.
- Message list endpoint has no ownership check and may fetch by any conversation id.

### C. Background ingestion robustness
- Background task closes over `target` path from request context and performs work inline in app process; this is brittle under reload/restarts.
- Ingestion status is binary (`ready/failed`), no error reason column, making operator debugging difficult.

### D. Frontend UX/runtime inefficiencies
- Static UI keeps substantial state in one file and manually syncs conversations/messages/PDF state; high risk of desync and hard debugging.
- Limited optimistic updates and weak invalidation strategy (full reload patterns).

---

## 3) Structural risks

### A. Tight coupling in `chat.py`
- Router handles HTTP, auth-derived ownership, retrieval orchestration, prompt policy, SSE framing, persistence, and trace logging in one module.
- Hard to test components independently and high regression probability.

### B. Ownership model via traces (implicit ACL)
- Access control depends on presence of `trace_events` payloads instead of explicit relational ownership table.
- Renames/deletes rely on event-history integrity; if logs are missing/corrupt, access behavior becomes inconsistent.

### C. RAG pipeline not modular enough
- Ingestion and retrieval policy logic is spread across router/service with minimal strategy abstraction.
- No explicit retriever interface (vector + lexical + hybrid rerank), limiting safe evolution.

### D. Prompt rigidity
- Mode prompts are static in code with concatenated directives at runtime; no template versioning, no audit trail per response.

### E. Observability gaps
- No structured error taxonomy for ingestion/retrieval failures in DB.
- No per-stage timing metrics (extract/chunk/embed/upsert/retrieve/generate).

---

## 4) High-impact refactor plan (concrete)

### Priority 1 — Access control and conversation ownership
1. Add `conversation_members` table (`conversation_id`, `user_id`, `role`, timestamps).
2. On conversation create, insert owner membership row.
3. Replace trace-based ownership checks with membership joins.
4. Enforce ownership check on `GET /conversations/{id}/messages` and stream endpoint.

### Priority 2 — RAG pipeline modularization
1. Introduce interfaces:
   - `EmbedProvider`
   - `VectorIndex`
   - `ChunkStore`
   - `Retriever` (hybrid strategy)
2. Move orchestration from router into `ChatService.generate_reply(...)`.
3. Add retrieval plan object:
   - query embedding cache key
   - doc filter
   - vector depth
   - lexical fallback policy

### Priority 3 — Performance and caching
1. Batch embeddings by chunk groups (configurable batch size).
2. Add in-memory LRU cache for query embeddings and top-k retrieval payloads.
3. Add DB indexes:
   - `messages(conversation_id, created_at)`
   - `trace_events(user_id, event_type, created_at)`
   - `pdf_documents(status, created_at)`

### Priority 4 — UX quality-of-life upgrades
1. Split static UI logic into modules (or move to existing Next.js app as canonical UI).
2. Add explicit ingestion diagnostics in UI (failed reason + retry button).
3. Persist selected PDF set per conversation.
4. Add progressive status chips: `processing -> ready_partial -> ready_vector -> failed`.

### Priority 5 — Reliability
1. Replace `BackgroundTasks` ingestion with durable worker queue (RQ/Celery or sqlite-backed job table + worker loop).
2. Persist ingestion errors (`last_error`, `ingested_chunks`, `vectorized_chunks`).

---

## 5) Immediate “quick wins” (low risk)

1. Add ownership checks on message list and stream.
2. Add `last_error` column in `pdf_documents`.
3. Cache query embedding for short TTL (e.g., 120s) to reduce repeated round trips.
4. Introduce timing logs for retrieval and generation phases.

---

## 6) Proposed implementation sequence

1. **Data model safety**: migration for explicit conversation membership + pdf ingestion diagnostics.
2. **Service extraction**: move stream orchestration to `services/chat_orchestrator.py`.
3. **Retriever abstraction**: split vector and lexical retrievers, then hybrid combiner.
4. **Performance pass**: embed batching + LRU caches + indexes.
5. **UX pass**: per-conversation PDF context, retry ingestion button, richer status timeline.

---

## 7) Definition of done for Phase 2

- P95 retrieval latency reduced by >=30% on same corpus.
- No trace-based ACL dependency for conversations.
- Ingestion failures diagnosable from UI without reading server logs.
- Chat with multi-PDF context consistently cites at least 2 selected docs when available.
