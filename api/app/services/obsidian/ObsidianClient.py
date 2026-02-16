from dataclasses import dataclass
from datetime import datetime

from app.services.obsidian.ObsidianSource import ObsidianConfig
from app.services.obsidian.adapters.FileSystemAdapter import FileSystemAdapter
from app.services.obsidian.adapters.LocalRestApiAdapter import LocalRestApiAdapter


@dataclass
class ObsidianSaveOptions:
    mode: str = "manual-only"  # per-message | daily-note-append | manual-only | canonical-only
    target_folder: str = "ChatEPS"
    include_sources: bool = True
    include_trace: bool = True
    include_retrieved_summary: bool = False


class ObsidianClient:
    def __init__(self, config: ObsidianConfig):
        self.config = config
        self.fs = FileSystemAdapter(
            vault_path=config.vault_path or "",
            included_folders=config.included_folders,
            excluded_folders=config.excluded_folders,
            excluded_patterns=config.excluded_patterns,
            max_notes_to_index=config.max_notes_to_index,
            max_note_bytes=config.max_note_bytes,
        )
        self.rest = LocalRestApiAdapter(config.rest_api_base_url or "", config.api_key or "")

    async def status(self) -> dict:
        fs_status = self.fs.health()
        rest_status = await self.rest.health() if self.config.mode == "rest" else {"ok": False, "mode": "rest"}
        return {
            "rest": rest_status,
            "filesystem": fs_status,
            "active": "rest" if rest_status.get("ok") else ("filesystem" if fs_status.get("ok") else "none"),
        }

    async def _active(self):
        if self.config.mode == "rest":
            st = await self.rest.health()
            if st.get("ok"):
                return "rest"
        if self.fs.is_ready():
            return "filesystem"
        return "none"

    async def create_note(self, path: str, content: str) -> dict:
        active = await self._active()
        if active == "rest":
            saved = await self.rest.create_note(path, content)
            return {"ok": True, "adapter": "rest", "path": saved, "open_uri": self.fs.open_uri(saved)}
        if active == "filesystem":
            saved = self.fs.create_note(path, content)
            return {"ok": True, "adapter": "filesystem", "path": saved, "open_uri": self.fs.open_uri(saved)}
        return {"ok": False, "error": "Aucun connecteur Obsidian disponible"}

    async def append_note(self, path: str, content: str) -> dict:
        active = await self._active()
        if active == "rest":
            saved = await self.rest.append_to_note(path, content)
            return {"ok": True, "adapter": "rest", "path": saved, "open_uri": self.fs.open_uri(saved)}
        if active == "filesystem":
            saved = self.fs.append_to_note(path, content)
            return {"ok": True, "adapter": "filesystem", "path": saved, "open_uri": self.fs.open_uri(saved)}
        return {"ok": False, "error": "Aucun connecteur Obsidian disponible"}

    async def search(self, query: str, filters: dict | None = None) -> list[dict]:
        active = await self._active()
        if active == "rest":
            result = await self.rest.search_notes(query, limit=filters.get("limit", 10) if filters else 10)
            return [
                {
                    "source": "obsidian",
                    "file_path": r.get("filename") or r.get("path") or r.get("file") or "",
                    "note_title": r.get("title") or r.get("filename") or "",
                    "text": r.get("snippet") or r.get("excerpt") or "",
                }
                for r in result
            ]
        return [
            {
                "source": "obsidian",
                "file_path": r["path"],
                "note_title": r["title"],
                "text": r["snippet"],
            }
            for r in self.fs.search_notes(query, limit=filters.get("limit", 10) if filters else 10)
        ]

    @staticmethod
    def default_note_name(topic: str, short_id: str) -> str:
        d = datetime.utcnow().strftime("%Y-%m-%d")
        safe = FileSystemAdapter.sanitize_filename(topic or "knowledge")
        return f"{d} - {safe} - {short_id}.md"
