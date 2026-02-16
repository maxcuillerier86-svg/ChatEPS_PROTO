import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchAny, MatchValue, PointStruct, VectorParams

from app.core.config import settings
from app.services.ollama import embed_texts

DOC_TYPES = ("theory", "practice", "reflection", "artifacts")


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        start += max(1, chunk_size - overlap)
    return [c for c in chunks if c.strip()]


def optimize_chunk_params(text: str, doc_type: str) -> tuple[int, int]:
    n = len(text or "")
    if doc_type == "practice":
        return (700, 120)
    if doc_type == "reflection":
        return (650, 140)
    if doc_type == "artifacts":
        return (500, 100)
    if n > 12000:
        return (1000, 180)
    if n < 3000:
        return (600, 100)
    return (850, 140)


def infer_doc_type(title: str, tags: list[str] | None = None, sample_text: str = "") -> str:
    hay = " ".join([(title or ""), *(tags or []), (sample_text or "")]).lower()
    if any(k in hay for k in ["atelier", "grille", "rubrique", "template", "artefact", "artifact"]):
        return "artifacts"
    if any(k in hay for k in ["réflex", "metacog", "journal", "retour", "feedback"]):
        return "reflection"
    if any(k in hay for k in ["séance", "exercice", "drill", "plan", "mise en pratique", "volleyball", "gymnase"]):
        return "practice"
    return "theory"


def extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        pages.append((i, page.extract_text() or ""))
    return pages


def qdrant() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def _chunk_cache_dir() -> Path:
    p = Path(settings.storage_root) / "chunks"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_path(doc_id: int) -> Path:
    return _chunk_cache_dir() / f"{doc_id}.json"


def _save_local_chunks(doc_id: int, chunks: list[dict]):
    _cache_path(doc_id).write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")


def _load_local_chunks(doc_ids: list[int] | None = None) -> list[dict]:
    files = []
    if doc_ids:
        files = [_cache_path(did) for did in doc_ids if _cache_path(did).exists()]
    else:
        files = list(_chunk_cache_dir().glob("*.json"))

    out: list[dict] = []
    for f in files:
        try:
            out.extend(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _lexical_score(query: str, text: str) -> int:
    q_terms = {t for t in re.findall(r"\w+", query.lower()) if len(t) >= 3}
    if not q_terms:
        return 0
    t_terms = set(re.findall(r"\w+", (text or "").lower()))
    return len(q_terms.intersection(t_terms))


def _chunk_key(chunk: dict[str, Any]) -> str:
    base = f"{chunk.get('doc_id')}|{chunk.get('page')}|{chunk.get('text','')[:120]}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def _metadata_match(chunk: dict[str, Any], metadata_filters: dict[str, Any] | None) -> bool:
    if not metadata_filters:
        return True
    allowed_types = metadata_filters.get("doc_types") or []
    if allowed_types and chunk.get("doc_type") not in allowed_types:
        return False
    required_tags = {t.lower() for t in (metadata_filters.get("tags") or [])}
    if required_tags:
        chunk_tags = {t.lower() for t in (chunk.get("tags") or [])}
        if not (required_tags & chunk_tags):
            return False
    return True


def _intent_doc_type_bonus(intent: str, doc_type: str) -> float:
    mapping = {
        "lesson_design": {"practice": 0.35, "theory": 0.15},
        "reflection": {"reflection": 0.4},
        "evaluation": {"artifacts": 0.35, "practice": 0.1},
        "explanation": {"theory": 0.25},
    }
    return mapping.get(intent, {}).get(doc_type, 0.0)


async def ensure_collection(vector_size: int = 768):
    client = qdrant()
    collections = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in collections:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


async def ingest_document(doc_id: int, path: Path, title: str, metadata: dict[str, Any] | None = None):
    metadata = metadata or {}
    tags = metadata.get("tags") or []

    pages = extract_pdf_pages(path)
    sample_text = " ".join([(p[1] or "")[:350] for p in pages[:2]])
    doc_type = metadata.get("doc_type") or infer_doc_type(title, tags, sample_text)

    page_chunks = []
    for page, text in pages:
        csize, overlap = optimize_chunk_params(text, doc_type)
        for chunk in chunk_text(text, chunk_size=csize, overlap=overlap):
            page_chunks.append(
                {
                    "page": page,
                    "text": chunk,
                    "doc_id": doc_id,
                    "title": title,
                    "doc_type": doc_type,
                    "tags": tags,
                    "course_id": metadata.get("course_id"),
                }
            )

    if not page_chunks:
        return

    _save_local_chunks(doc_id, page_chunks)

    try:
        vectors = await embed_texts([c["text"] for c in page_chunks])
        await ensure_collection(len(vectors[0]))
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=chunk,
            )
            for vector, chunk in zip(vectors, page_chunks)
        ]
        qdrant().upsert(collection_name=settings.qdrant_collection, points=points)
    except Exception:
        pass


def _coarse_lexical_retrieve(
    query: str,
    expanded_queries: list[str],
    doc_ids: list[int] | None,
    metadata_filters: dict[str, Any] | None,
    limit: int,
) -> list[dict]:
    chunks = _load_local_chunks(doc_ids)
    if not chunks:
        return []
    weighted_queries = [query, *expanded_queries]
    ranked: list[tuple[float, dict]] = []
    for ch in chunks:
        if not _metadata_match(ch, metadata_filters):
            continue
        score = 0.0
        for i, q in enumerate(weighted_queries):
            weight = 1.0 if i == 0 else 0.5
            score += weight * _lexical_score(q, ch.get("text", ""))
        if score > 0:
            ranked.append((score, ch))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [ch for _, ch in ranked[:limit]]


async def _vector_retrieve(
    query: str,
    expanded_queries: list[str],
    doc_ids: list[int] | None,
    metadata_filters: dict[str, Any] | None,
    limit: int,
) -> list[dict]:
    queries = [query, *expanded_queries[:2]]
    vectors = await embed_texts(queries)
    if not vectors:
        return []

    flt_conditions = []
    if doc_ids:
        flt_conditions.append(FieldCondition(key="doc_id", match=MatchAny(any=doc_ids)))
    if metadata_filters and metadata_filters.get("doc_types"):
        flt_conditions.append(FieldCondition(key="doc_type", match=MatchAny(any=metadata_filters["doc_types"])))

    qfilter = Filter(must=flt_conditions) if flt_conditions else None

    gathered: list[dict] = []
    for vec in vectors:
        hits = qdrant().search(
            collection_name=settings.qdrant_collection,
            query_vector=vec,
            limit=limit,
            query_filter=qfilter,
        )
        gathered.extend([h.payload for h in hits if _metadata_match(h.payload, metadata_filters)])
    return gathered


def _rerank_candidates(
    query: str,
    candidates: list[dict],
    intent: str,
    top_k: int,
) -> list[dict]:
    scored: list[tuple[float, dict]] = []
    seen: set[str] = set()
    for ch in candidates:
        key = _chunk_key(ch)
        if key in seen:
            continue
        seen.add(key)
        lexical = _lexical_score(query, ch.get("text", ""))
        bonus = _intent_doc_type_bonus(intent, ch.get("doc_type", "theory"))
        score = float(lexical) + bonus
        scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ch for _, ch in scored[:top_k]]


def compress_context(hits: list[dict], max_chars: int = 1600) -> list[dict]:
    compressed: list[dict] = []
    budget = max_chars
    for h in hits:
        text = (h.get("text") or "").strip()
        if not text:
            continue
        sentences = re.split(r"(?<=[\.!?])\s+", text)
        picked = []
        local_budget = min(320, budget)
        for s in sentences:
            if len(" ".join(picked + [s])) > local_budget:
                break
            picked.append(s)
            if len(picked) >= 2:
                break
        excerpt = " ".join(picked).strip() or text[: min(260, budget)]
        if not excerpt:
            continue
        item = {
            "source": h.get("source", "pdf"),
            "doc_id": h.get("doc_id"),
            "title": h.get("title"),
            "note_title": h.get("note_title"),
            "file_path": h.get("file_path"),
            "heading": h.get("heading"),
            "page": h.get("page"),
            "doc_type": h.get("doc_type", h.get("note_type", "theory")),
            "note_type": h.get("note_type"),
            "excerpt": excerpt,
            "text": excerpt,
            "tags": h.get("tags") or [],
            "_score": h.get("_score", 0.0),
            "_fused_score": h.get("_fused_score", h.get("_score", 0.0)),
            "modified_at": h.get("modified_at"),
        }
        if len(excerpt) + 4 > budget:
            break
        compressed.append(item)
        budget -= len(excerpt) + 4
        if budget <= 100:
            break
    return compressed


async def retrieve(
    query: str,
    doc_ids: list[int] | None = None,
    top_k: int = 4,
    expanded_queries: list[str] | None = None,
    intent: str = "unknown",
    metadata_filters: dict[str, Any] | None = None,
):
    expanded_queries = [q for q in (expanded_queries or []) if q and q.strip()]
    coarse = _coarse_lexical_retrieve(query, expanded_queries, doc_ids, metadata_filters, limit=max(top_k * 4, 10))

    vector_hits: list[dict] = []
    try:
        vector_hits = await _vector_retrieve(
            query,
            expanded_queries,
            doc_ids,
            metadata_filters,
            limit=max(top_k * 3, 8),
        )
    except Exception:
        vector_hits = []

    merged = [*coarse, *vector_hits]
    if not merged:
        return []
    reranked = _rerank_candidates(query, merged, intent=intent, top_k=top_k)
    return reranked


async def remove_document_chunks(doc_id: int):
    try:
        cp = _cache_path(doc_id)
        if cp.exists():
            cp.unlink()
    except Exception:
        pass

    try:
        qdrant().delete(
            collection_name=settings.qdrant_collection,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )
    except Exception:
        pass
