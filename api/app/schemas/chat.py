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


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    metadata_json: dict | None

    class Config:
        from_attributes = True
