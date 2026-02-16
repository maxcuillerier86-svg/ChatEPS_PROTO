import sqlite3

import httpx
from fastapi import APIRouter
from qdrant_client import QdrantClient

from app.core.config import settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
async def health():
    status = {"api": "ok", "ollama": "down", "qdrant": "down", "storage": "ok", "db": "ok"}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.ollama_url}/api/tags")
            if r.status_code == 200:
                status["ollama"] = "ok"
    except Exception:
        pass
    try:
        QdrantClient(url=settings.qdrant_url).get_collections()
        status["qdrant"] = "ok"
    except Exception:
        pass
    try:
        if settings.database_url.startswith("sqlite"):
            sqlite3.connect(settings.database_url.replace("sqlite:///", "")).close()
    except Exception:
        status["db"] = "down"
    return status
