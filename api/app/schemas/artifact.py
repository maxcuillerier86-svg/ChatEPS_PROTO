from pydantic import BaseModel


class ArtifactCreate(BaseModel):
    title: str
    content_md: str = ""
    conversation_id: int | None = None


class ArtifactUpdate(BaseModel):
    content_md: str
    status: str = "brouillon"
