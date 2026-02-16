from pathlib import Path

import httpx


class LocalRestApiAdapter:
    def __init__(self, base_url: str, api_key: str, timeout_s: int = 15):
        self.base_url = (base_url or "http://127.0.0.1:27124").rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s

    @property
    def _headers(self) -> dict[str, str]:
        h = {}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for ep in ["/health", "/"]:
                try:
                    r = await client.get(f"{self.base_url}{ep}", headers=self._headers)
                    if r.status_code < 400:
                        return {"ok": True, "mode": "rest", "base_url": self.base_url}
                except Exception:
                    continue
        return {"ok": False, "mode": "rest", "base_url": self.base_url}

    async def list_notes(self) -> list[str]:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for endpoint in ["/vault/", "/vault/files", "/files"]:
                try:
                    r = await client.get(f"{self.base_url}{endpoint}", headers=self._headers)
                    if r.status_code >= 400:
                        continue
                    data = r.json()
                    raw = data if isinstance(data, list) else (data.get("files") or data.get("items") or [])
                    return [str(x) for x in raw if str(x).endswith(".md")]
                except Exception:
                    continue
        return []

    async def read_note(self, note_path: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            quoted = str(Path(note_path)).replace("\\", "/")
            for endpoint in [f"/vault/{quoted}", f"/vault/file/{quoted}", f"/file/{quoted}"]:
                try:
                    r = await client.get(f"{self.base_url}{endpoint}", headers=self._headers)
                    if r.status_code >= 400:
                        continue
                    if "application/json" in r.headers.get("content-type", ""):
                        d = r.json()
                        return d.get("content") or d.get("text") or ""
                    return r.text
                except Exception:
                    continue
        return ""

    async def create_note(self, note_path: str, content: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for endpoint in [f"/vault/{note_path}", f"/vault/file/{note_path}", f"/file/{note_path}"]:
                try:
                    r = await client.put(f"{self.base_url}{endpoint}", headers=self._headers, content=content.encode("utf-8"))
                    if r.status_code < 400:
                        return note_path
                except Exception:
                    continue
        raise RuntimeError("REST create_note indisponible")

    async def append_to_note(self, note_path: str, content: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for endpoint in [f"/vault/{note_path}", f"/vault/file/{note_path}", f"/file/{note_path}"]:
                try:
                    r = await client.post(f"{self.base_url}{endpoint}", headers=self._headers, content=content.encode("utf-8"))
                    if r.status_code < 400:
                        return note_path
                except Exception:
                    continue
        raise RuntimeError("REST append_to_note indisponible")

    async def search_notes(self, query: str, limit: int = 10) -> list[dict]:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for endpoint in ["/search/simple", "/search"]:
                try:
                    r = await client.get(
                        f"{self.base_url}{endpoint}",
                        headers=self._headers,
                        params={"query": query, "limit": limit},
                    )
                    if r.status_code >= 400:
                        continue
                    data = r.json()
                    if isinstance(data, list):
                        return data[:limit]
                    return (data.get("results") or data.get("items") or [])[:limit]
                except Exception:
                    continue
        return []
