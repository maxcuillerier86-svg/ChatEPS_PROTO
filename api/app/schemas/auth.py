from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "student"


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str

    class Config:
        from_attributes = True
