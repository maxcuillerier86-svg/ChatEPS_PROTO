import time
from collections import OrderedDict

import httpx

from app.core.config import settings

_EMBED_CACHE_MAX = 1500
_EMBED_CACHE_TTL_S = 60 * 30
_embed_cache: OrderedDict[tuple[str, str], tuple[float, list[float]]] = OrderedDict()


def _cache_get(model: str, text: str) -> list[float] | None:
    key = (model, text)
    found = _embed_cache.get(key)
    if not found:
        return None
    ts, value = found
    if time.time() - ts > _EMBED_CACHE_TTL_S:
        _embed_cache.pop(key, None)
        return None
    _embed_cache.move_to_end(key)
    return value


def _cache_set(model: str, text: str, vector: list[float]):
    key = (model, text)
    _embed_cache[key] = (time.time(), vector)
    _embed_cache.move_to_end(key)
    while len(_embed_cache) > _EMBED_CACHE_MAX:
        _embed_cache.popitem(last=False)


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


def _is_model_not_found(resp: httpx.Response) -> bool:
    body = (resp.text or "").lower()
    return "model" in body and "not" in body and "found" in body


async def _embed_via_legacy(client: httpx.AsyncClient, text: str, model: str) -> list[float]:
    resp = await client.post(
        f"{settings.ollama_url}/api/embeddings",
        json={"model": model, "prompt": text},
    )
    resp.raise_for_status()
    data = resp.json()
    vector = data.get("embedding")
    if not vector:
        raise ValueError("Réponse /api/embeddings sans embedding")
    return vector


async def _embed_via_current(client: httpx.AsyncClient, text: str, model: str) -> list[float]:
    resp = await client.post(
        f"{settings.ollama_url}/api/embed",
        json={"model": model, "input": text},
    )
    resp.raise_for_status()
    data = resp.json()
    embeds = data.get("embeddings") or []
    if not embeds:
        raise ValueError("Réponse /api/embed sans embeddings")
    return embeds[0]


async def _attempt_pull_model(client: httpx.AsyncClient, model: str):
    resp = await client.post(
        f"{settings.ollama_url}/api/pull",
        json={"name": model, "stream": False},
        timeout=600,
    )
    resp.raise_for_status()


async def _embed_one_text(client: httpx.AsyncClient, text: str, model: str) -> list[float]:
    cached = _cache_get(model, text)
    if cached is not None:
        return cached
    try:
        vector = await _embed_via_legacy(client, text, model)
    except httpx.HTTPStatusError as exc_legacy:
        if exc_legacy.response.status_code == 404:
            vector = await _embed_via_current(client, text, model)
        else:
            raise
    _cache_set(model, text, vector)
    return vector


async def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    model_candidates = [settings.ollama_embedding_model]
    if settings.ollama_chat_model not in model_candidates:
        model_candidates.append(settings.ollama_chat_model)

    async with httpx.AsyncClient(timeout=120) as client:
        for text in texts:
            if not text or not text.strip():
                continue
            last_exc: Exception | None = None
            embedded = False
            for model in model_candidates:
                for attempt in range(2):
                    try:
                        embeddings.append(await _embed_one_text(client, text, model))
                        embedded = True
                        break
                    except httpx.HTTPStatusError as exc:
                        last_exc = exc
                        if attempt == 0 and _is_model_not_found(exc.response):
                            await _attempt_pull_model(client, model)
                            continue
                        if exc.response.status_code in (404, 400, 422) and _is_model_not_found(exc.response):
                            break
                        raise
                if embedded:
                    break
            if not embedded:
                if last_exc:
                    raise last_exc
                raise RuntimeError("Aucun embedding produit")
    return embeddings
