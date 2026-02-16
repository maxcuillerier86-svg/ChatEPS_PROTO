# Obsidian Vault Integration for ChatEPS RAG

## What was added
- New **Obsidian source adapters**:
  - filesystem vault ingestion
  - Obsidian Local REST API ingestion
- Incremental indexing manifest (`data/obsidian_manifest.json`) using file hash + modified time.
- Obsidian-aware retrieval with metadata filters (`tags`, `noteType`, `course`, `language`, `recency_days`).
- Fusion with existing PDF results and source-transparent citations in chat output.
- UI controls for:
  - configuring vault/REST connection
  - running indexing
  - toggling `Use Obsidian` / `Prefer Obsidian`
  - filtering by tag, note type, timeframe

## Local-first security posture
- Vault content stays local.
- `.obsidian/`, `templates/`, `attachments/` excluded by default.
- Obsidian URI used only as convenience "open note" link.

## API endpoints
- `GET /obsidian/config`
- `POST /obsidian/config`
- `GET /obsidian/status`
- `POST /obsidian/index`

## Notes on incremental indexing
- On each indexing run:
  1. discover notes
  2. compute file hash
  3. re-index only changed notes
  4. remove vectors for deleted notes
