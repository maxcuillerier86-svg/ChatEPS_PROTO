from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import artifacts, auth, chat, dashboard, library, system

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Path(settings.storage_root).mkdir(parents=True, exist_ok=True)
Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(library.router)
app.include_router(artifacts.router)
app.include_router(dashboard.router)
app.include_router(system.router)


@app.get("/")
def root():
    return {"name": "Co-PE API", "status": "running"}
