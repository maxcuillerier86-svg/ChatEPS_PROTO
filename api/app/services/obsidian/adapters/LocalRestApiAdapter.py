from __future__ import annotations

from datetime import datetime

import httpx

from app.services.obsidian.types import ObsidianConfig, ObsidianNote


class LocalRestApiAdapter:
    def __init__(self, cfg: ObsidianConfig):
        self.cfg = cfg

    async def read_notes(self) -> list[ObsidianNote]:
        if not self.cfg.rest_api_base_url or not self.cfg.api_key:
            return []
        base = self.cfg.rest_api_base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {self.cfg.api_key}"}

        async with httpx.AsyncClient(timeout=30) as client:
            files_resp = await client.get(f"{base}/vault/", headers=headers)
            files_resp.raise_for_status()
            files = [f for f in (files_resp.json().get("files") or []) if isinstance(f, str) and f.endswith(".md")]

            out: list[ObsidianNote] = []
            for rel in files:
                if self.cfg.included_folders and not any(rel.startswith(f.strip("/") + "/") or rel == f.strip("/") for f in self.cfg.included_folders):
                    continue
                if any(rel.startswith(x.strip("/") + "/") or rel == x.strip("/") for x in self.cfg.excluded_folders):
                    continue

                resp = await client.get(f"{base}/vault/{rel}", headers=headers)
                if resp.status_code >= 400:
                    continue
                content = resp.text
                if len(content.encode("utf-8")) > self.cfg.max_note_bytes:
                    continue

                md = {}
                try:
                    meta = await client.get(f"{base}/metadata/{rel}", headers=headers)
                    if meta.status_code < 400:
                        md = meta.json() if isinstance(meta.json(), dict) else {}
                except Exception:
                    md = {}

                out.append(
                    ObsidianNote(
                        path=rel,
                        content=content,
                        title=rel.split("/")[-1].rsplit(".", 1)[0],
                        metadata=md,
                        modified_at=datetime.fromisoformat(md.get("mtime")) if md.get("mtime") else None,
                        created_at=datetime.fromisoformat(md.get("ctime")) if md.get("ctime") else None,
                    )
                )
                if len(out) >= self.cfg.max_notes_to_index:
                    break
        return out
