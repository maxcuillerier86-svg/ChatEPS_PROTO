from pathlib import Path

import httpx


class LocalRestApiAdapter:
    def __init__(self, base_url: str, api_key: str, timeout_s: int = 15):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    async def list_notes(self) -> list[str]:
        # Obsidian Local REST API plugin variants differ; try common endpoints.
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for endpoint in ["/vault/", "/vault/files", "/files"]:
                try:
                    r = await client.get(f"{self.base_url}{endpoint}", headers=self._headers)
                    if r.status_code >= 400:
                        continue
                    data = r.json()
                    if isinstance(data, list):
                        items = [str(x) for x in data]
                    elif isinstance(data, dict):
                        raw = data.get("files") or data.get("items") or []
                        items = [str(x) for x in raw]
                    else:
                        items = []
                    return [x for x in items if x.endswith(".md")]
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
                    ct = r.headers.get("content-type", "")
                    if "application/json" in ct:
                        data = r.json()
                        return data.get("content") or data.get("text") or ""
                    return r.text
                except Exception:
                    continue
        return ""
