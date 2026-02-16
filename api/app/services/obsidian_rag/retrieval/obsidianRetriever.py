from typing import Any

from qdrant_client.http.models import FieldCondition, Filter, MatchAny, MatchValue

from app.core.config import settings
from app.services.obsidian.filters.metadataFilters import apply_obsidian_filters
from app.services.ollama import embed_texts
from app.services.rag import qdrant


async def retrieve_obsidian(
    query: str,
    top_k: int = 6,
    filters: dict[str, Any] | None = None,
    prefer_obsidian: bool = False,
) -> list[dict]:
    vector = (await embed_texts([query]))[0]

    must = [FieldCondition(key="source", match=MatchValue(value="obsidian"))]
    if filters and filters.get("tags"):
        must.append(FieldCondition(key="tags", match=MatchAny(any=filters["tags"])))
    if filters and (filters.get("noteType") or filters.get("note_type")):
        nts = filters.get("noteType") or filters.get("note_type")
        must.append(FieldCondition(key="note_type", match=MatchAny(any=nts)))
    if filters and filters.get("course"):
        must.append(FieldCondition(key="course", match=MatchAny(any=filters["course"])))

    hits = qdrant().search(
        collection_name=settings.qdrant_collection,
        query_vector=vector,
        limit=top_k * 2,
        query_filter=Filter(must=must),
    )

    out = []
    for h in hits:
        payload = h.payload or {}
        payload["_score"] = float(getattr(h, "score", 0.0))
        if prefer_obsidian:
            payload["_score"] += 0.08
        out.append(payload)

    out = apply_obsidian_filters(out, filters)
    out.sort(key=lambda x: x.get("_score", 0.0), reverse=True)
    return out[:top_k]
