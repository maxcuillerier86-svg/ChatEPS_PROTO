from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user
from app.models.entities import PdfDocument, User
from app.schemas.pdf import PdfOut
from app.services.rag import ingest_document
from app.services.tracing import log_event

router = APIRouter(prefix="/library", tags=["library"])


@router.post("/upload", response_model=PdfOut)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    tags: str = Form(""),
    course_id: int | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Seuls les PDF sont autorisés")
    storage = Path(settings.storage_root) / "pdfs"
    storage.mkdir(parents=True, exist_ok=True)
    target = storage / file.filename
    target.write_bytes(await file.read())

    doc = PdfDocument(
        title=title,
        filename=file.filename,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        course_id=course_id,
        uploaded_by_id=user.id,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    async def _ingest(doc_id: int):
        await ingest_document(doc_id, target, title)
        inner_db = SessionLocal()
        try:
            d = inner_db.query(PdfDocument).filter(PdfDocument.id == doc_id).first()
            if d:
                d.status = "ready"
                inner_db.commit()
        finally:
            inner_db.close()

    background_tasks.add_task(_ingest, doc.id)
    log_event(db, user.id, "pdf_upload", {"doc_id": doc.id, "title": title})
    return doc


@router.get("/documents", response_model=list[PdfOut])
def list_docs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(PdfDocument).all()
