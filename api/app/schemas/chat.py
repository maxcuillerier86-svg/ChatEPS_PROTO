from typing import Any

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str
    mode: str = "exploration_novice"
    type: str = "private"
    course_id: int | None = None


class MessageIn(BaseModel):
    content: str
    use_rag: bool = True
    collection_ids: list[int] = Field(default_factory=list)
    model: str | None = None
    student_level: str | None = "novice"
    confidence: int | None = None
    strict_grounding: bool = True
    metadata_filters: dict[str, Any] | None = None
    use_obsidian: bool = True
    prefer_obsidian: bool = False
    obsidian_filters: dict[str, Any] | None = None
    autosave_to_obsidian: bool = False
    obsidian_save_mode: str = "manual-only"  # per-message | daily-note-append | manual-only | canonical-only
    obsidian_target_folder: str | None = None
    obsidian_config: dict[str, Any] | None = None
    mark_canonical: bool = False
    include_sources_in_save: bool = True
    include_trace_in_save: bool = True
    include_retrieved_summary_in_save: bool = False


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    metadata_json: dict | None

    class Config:
        from_attributes = True
