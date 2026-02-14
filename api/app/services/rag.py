import json
import re
import uuid
from pathlib import Path

from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from app.core.config import settings
from app.services.ollama import embed_texts


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


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


async def ensure_collection(vector_size: int = 768):
    client = qdrant()
    collections = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in collections:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


async def ingest_document(doc_id: int, path: Path, title: str):
    page_chunks = []
    for page, text in extract_pdf_pages(path):
        for chunk in chunk_text(text):
            page_chunks.append({"page": page, "text": chunk, "doc_id": doc_id, "title": title})

    if not page_chunks:
        return

    # Toujours garder une copie locale: permet une recherche lexicale de secours
    _save_local_chunks(doc_id, page_chunks)

    # Ingestion vectorielle (best-effort)
    try:
        vectors = await embed_texts([c["text"] for c in page_chunks])
        await ensure_collection(len(vectors[0]))
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "doc_id": ch["doc_id"],
                    "title": ch["title"],
                    "page": ch["page"],
                    "text": ch["text"],
                },
            )
            for vector, ch in zip(vectors, page_chunks)
        ]
        qdrant().upsert(collection_name=settings.qdrant_collection, points=points)
    except Exception:
        # On laisse la voie locale active même si embeddings/Qdrant indisponibles.
        pass


async def retrieve(query: str, doc_ids: list[int] | None = None, top_k: int = 4):
    # 1) tentative vectorielle
    try:
        vector = (await embed_texts([query]))[0]
        flt = None
        if doc_ids:
            from qdrant_client.http.models import FieldCondition, Filter, MatchAny

            flt = Filter(must=[FieldCondition(key="doc_id", match=MatchAny(any=doc_ids))])
        hits = qdrant().search(collection_name=settings.qdrant_collection, query_vector=vector, limit=top_k, query_filter=flt)
        payloads = [h.payload for h in hits]
        if payloads:
            return payloads
    except Exception:
        pass

    # 2) fallback local lexical
    chunks = _load_local_chunks(doc_ids)
    ranked = []
    for ch in chunks:
        score = _lexical_score(query, ch.get("text", ""))
        if score > 0:
            ranked.append((score, ch))
    ranked.sort(key=lambda x: x[0], reverse=True)
    if ranked:
        return [ch for _, ch in ranked[:top_k]]
    return chunks[:top_k]


async def remove_document_chunks(doc_id: int):
    try:
        cp = _cache_path(doc_id)
        if cp.exists():
            cp.unlink()
    except Exception:
        pass

    try:
        from qdrant_client.http.models import FieldCondition, Filter, MatchValue

        qdrant().delete(
            collection_name=settings.qdrant_collection,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )
    except Exception:
        pass
