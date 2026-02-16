from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ObsidianNote:
    path: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    note_type: str | None = None
    course: str | None = None
    status: str | None = None
    language: str | None = None
    headings: list[str] = field(default_factory=list)
    wikilinks: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    modified_at: datetime | None = None
    frontmatter: dict[str, Any] = field(default_factory=dict)


@dataclass
class ObsidianChunk:
    id: str
    path: str
    note_title: str
    heading: str | None
    text: str
    tags: list[str]
    note_type: str | None
    course: str | None
    status: str | None
    language: str | None
    modified_at: str | None


@dataclass
class ObsidianIngestStats:
    indexed: int = 0
    skipped: int = 0
    deleted: int = 0
    errors: int = 0
