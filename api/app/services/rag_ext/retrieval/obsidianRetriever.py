from __future__ import annotations

from app.core.config import settings
from app.services.obsidian.filters.metadataFilters import apply_metadata_filters, recency_boost
from app.services.ollama import embed_texts
from app.services.rag import qdrant


def _normalize(scores: list[float]) -> list[float]:
    if not scores:
        return []
    mn = min(scores)
    mx = max(scores)
    if mx - mn < 1e-9:
        return [1.0 for _ in scores]
    return [(s - mn) / (mx - mn) for s in scores]


async def retrieve_obsidian(
    query: str,
    top_k: int = 6,
    metadata_filters: dict | None = None,
    prefer_obsidian: bool = False,
) -> list[dict]:
    vector = (await embed_texts([query]))[0]
    hits = qdrant().search(collection_name=settings.qdrant_collection, query_vector=vector, limit=max(20, top_k * 3))
    obs = []
    for h in hits:
        pl = h.payload or {}
        if pl.get("source") != "obsidian":
            continue
        item = {
            "source": "obsidian",
            "score_raw": float(getattr(h, "score", 0.0) or 0.0),
            "text": pl.get("text", ""),
            "title": pl.get("noteTitle") or pl.get("title") or "Note Obsidian",
            "file_path": pl.get("filePath"),
            "heading": pl.get("heading"),
            "doc_id": pl.get("doc_id") or pl.get("filePath"),
            "page": pl.get("page", 1),
            "tags": pl.get("tags") or [],
            "note_type": pl.get("note_type"),
            "modified_at": pl.get("modified_at"),
            "metadata": pl,
        }
        obs.append(item)

    obs = apply_metadata_filters(obs, metadata_filters)
    if not obs:
        return []

    raw_scores = [x["score_raw"] for x in obs]
    norm = _normalize(raw_scores)
    for item, ns in zip(obs, norm):
        score = ns + recency_boost(item.get("modified_at"))
        if metadata_filters:
            tags = {t.lower() for t in (metadata_filters.get("tags") or [])}
            itags = {str(t).lower() for t in (item.get("tags") or [])}
            if tags and (tags & itags):
                score += 0.12
            nts = {t.lower() for t in (metadata_filters.get("noteType") or metadata_filters.get("note_types") or [])}
            if nts and str(item.get("note_type") or "").lower() in nts:
                score += 0.10
        if prefer_obsidian:
            score += 0.12
        item["score"] = round(score, 4)

    obs.sort(key=lambda x: x.get("score", 0), reverse=True)
    return obs[:top_k]
