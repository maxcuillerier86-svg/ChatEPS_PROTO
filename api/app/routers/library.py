from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import get_actor_user
from app.models.entities import PdfDocument, User
from app.schemas.pdf import PdfOut
from app.services.rag import ingest_document, remove_document_chunks
from app.services.tracing import log_event

router = APIRouter(prefix="/library", tags=["library"])


def _pdf_storage_path(filename: str) -> Path:
    return Path(settings.storage_root) / "pdfs" / filename


@router.post("/upload", response_model=PdfOut)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    tags: str = Form(""),
    course_id: int | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_actor_user),
):
    if not file.filename.lower().endswith(".pdf"):
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
        inner_db = SessionLocal()
        try:
            d = inner_db.query(PdfDocument).filter(PdfDocument.id == doc_id).first()
            try:
                await ingest_document(doc_id, target, title)
                if d:
                    d.status = "ready"
            except Exception:
                if d:
                    d.status = "failed"
            inner_db.commit()
        finally:
            inner_db.close()

    background_tasks.add_task(_ingest, doc.id)
    log_event(db, user.id, "pdf_upload", {"doc_id": doc.id, "title": title})
    return doc


@router.get("/documents", response_model=list[PdfOut])
def list_docs(db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    return db.query(PdfDocument).order_by(PdfDocument.created_at.desc()).all()


@router.patch("/documents/{doc_id}", response_model=PdfOut)
def rename_doc(doc_id: int, payload: dict, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Nouveau titre requis")
    doc = db.query(PdfDocument).filter(PdfDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable")
    doc.title = title
    db.commit()
    db.refresh(doc)
    log_event(db, user.id, "pdf_rename", {"doc_id": doc.id, "title": title})
    return doc


@router.delete("/documents/{doc_id}")
async def delete_doc(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    doc = db.query(PdfDocument).filter(PdfDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable")

    filename = doc.filename
    db.delete(doc)
    db.commit()

    p = _pdf_storage_path(filename)
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass

    await remove_document_chunks(doc_id)
    log_event(db, user.id, "pdf_delete", {"doc_id": doc_id, "filename": filename})
    return {"ok": True}
