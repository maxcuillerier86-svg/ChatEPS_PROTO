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


async def retrieve(query: str, doc_ids: list[int] | None = None, top_k: int = 4):
    vector = (await embed_texts([query]))[0]
    flt = None
    if doc_ids:
        from qdrant_client.http.models import FieldCondition, Filter, MatchAny

        flt = Filter(must=[FieldCondition(key="doc_id", match=MatchAny(any=doc_ids))])
    hits = qdrant().search(collection_name=settings.qdrant_collection, query_vector=vector, limit=top_k, query_filter=flt)
    return [h.payload for h in hits]
