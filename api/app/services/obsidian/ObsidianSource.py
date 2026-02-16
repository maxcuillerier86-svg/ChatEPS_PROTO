from dataclasses import dataclass
from pathlib import Path

from app.services.obsidian.adapters.FileSystemAdapter import FileSystemAdapter
from app.services.obsidian.adapters.LocalRestApiAdapter import LocalRestApiAdapter


@dataclass
class ObsidianConfig:
    mode: str = "filesystem"  # filesystem | rest
    vault_path: str | None = None
    rest_api_base_url: str | None = None
    api_key: str | None = None
    included_folders: list[str] | None = None
    excluded_folders: list[str] | None = None
    excluded_patterns: list[str] | None = None
    max_notes_to_index: int = 5000
    max_note_bytes: int = 500_000
    incremental_indexing: bool = True


class ObsidianSource:
    def __init__(self, config: ObsidianConfig):
        self.config = config
        self.fs_adapter = None
        self.rest_adapter = None
        if config.mode == "rest":
            self.rest_adapter = LocalRestApiAdapter(config.rest_api_base_url or "http://127.0.0.1:27124", config.api_key or "")
        else:
            self.fs_adapter = FileSystemAdapter(
                vault_path=config.vault_path or "",
                included_folders=config.included_folders,
                excluded_folders=config.excluded_folders,
                excluded_patterns=config.excluded_patterns,
                max_notes_to_index=config.max_notes_to_index,
                max_note_bytes=config.max_note_bytes,
            )

    async def list_notes(self) -> list[str]:
        if self.rest_adapter:
            return await self.rest_adapter.list_notes()
        if self.fs_adapter:
            return [str(p) for p in self.fs_adapter.list_notes()]
        return []

    async def read_note(self, note_path: str) -> str:
        if self.rest_adapter:
            return await self.rest_adapter.read_note(note_path)
        if self.fs_adapter:
            return self.fs_adapter.read_note(Path(note_path))
        return ""
