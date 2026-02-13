from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str
    mode: str = "exploration_novice"
    type: str = "private"
    course_id: int | None = None


class MessageIn(BaseModel):
    content: str
    use_rag: bool = True
    collection_ids: list[int] = []
    model: str | None = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    metadata_json: dict | None

    class Config:
        from_attributes = True
