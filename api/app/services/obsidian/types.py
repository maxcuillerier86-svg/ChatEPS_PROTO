from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ObsidianNote:
    path: str
    content: str
    title: str
    metadata: dict[str, Any] = field(default_factory=dict)
    modified_at: datetime | None = None
    created_at: datetime | None = None


@dataclass
class ObsidianChunk:
    id: str
    text: str
    note_path: str
    note_title: str
    heading: str | None
    chunk_index: int
    metadata: dict[str, Any]


@dataclass
class ObsidianConfig:
    mode: str = "filesystem"  # filesystem|rest
    vault_path: str | None = None
    rest_api_base_url: str | None = None
    api_key: str | None = None
    included_folders: list[str] = field(default_factory=list)
    excluded_folders: list[str] = field(default_factory=lambda: [".obsidian", "templates", "attachments"])
    excluded_patterns: list[str] = field(default_factory=lambda: [".obsidian/**", "templates/**", "attachments/**"])
    max_notes_to_index: int = 5000
    max_note_bytes: int = 400_000
    default_metadata_filters: dict[str, Any] = field(default_factory=dict)
    incremental_indexing: bool = True
    vault_name: str = "default"
