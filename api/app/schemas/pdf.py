from pydantic import BaseModel


class PdfOut(BaseModel):
    id: int
    title: str
    status: str
    filename: str

    class Config:
        from_attributes = True
