import httpx

from app.core.config import settings


async def check_ollama() -> tuple[bool, str | None]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
        return True, None
    except Exception as exc:
        return False, str(exc)


async def chat_stream(messages: list[dict], model: str | None = None):
    payload = {"model": model or settings.ollama_chat_model, "messages": messages, "stream": True}
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{settings.ollama_url}/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    yield line


async def list_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
            names = [m.get("name") for m in resp.json().get("models", []) if m.get("name")]
            return names or [settings.ollama_chat_model]
    except Exception:
        return [settings.ollama_chat_model]


async def pull_model(model: str) -> dict:
    model = (model or "").strip()
    if not model:
        raise ValueError("Nom de modèle requis")
    async with httpx.AsyncClient(timeout=600) as client:
        resp = await client.post(
            f"{settings.ollama_url}/api/pull",
            json={"name": model, "stream": False},
        )
        resp.raise_for_status()
        return resp.json()


async def _embed_via_legacy(client: httpx.AsyncClient, text: str) -> list[float]:
    resp = await client.post(
        f"{settings.ollama_url}/api/embeddings",
        json={"model": settings.ollama_embedding_model, "prompt": text},
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


async def _embed_via_current(client: httpx.AsyncClient, text: str) -> list[float]:
    resp = await client.post(
        f"{settings.ollama_url}/api/embed",
        json={"model": settings.ollama_embedding_model, "input": text},
    )
    resp.raise_for_status()
    data = resp.json()
    embeds = data.get("embeddings") or []
    if not embeds:
        raise ValueError("Réponse /api/embed sans embeddings")
    return embeds[0]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    async with httpx.AsyncClient(timeout=120) as client:
        for text in texts:
            try:
                emb = await _embed_via_legacy(client, text)
            except httpx.HTTPStatusError as exc:
                # Some Ollama versions expose /api/embed instead of /api/embeddings
                if exc.response.status_code == 404:
                    emb = await _embed_via_current(client, text)
                else:
                    raise
            embeddings.append(emb)
    return embeddings
