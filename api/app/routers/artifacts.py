from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_actor_user
from app.models.entities import Artifact, ArtifactVersion, User
from app.schemas.artifact import ArtifactCreate, ArtifactUpdate
from app.services.tracing import log_event

router = APIRouter(prefix="/artefacts", tags=["artefacts"])


def _artifact_out(art: Artifact) -> dict:
    return {
        "id": art.id,
        "title": art.title,
        "content_md": art.content_md,
        "status": art.status,
        "owner_id": art.owner_id,
        "conversation_id": art.conversation_id,
        "created_at": art.created_at.isoformat() if art.created_at else None,
        "updated_at": art.updated_at.isoformat() if art.updated_at else None,
    }


def _version_out(v: ArtifactVersion) -> dict:
    return {
        "id": v.id,
        "artifact_id": v.artifact_id,
        "editor_id": v.editor_id,
        "content_md": v.content_md,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.post("")
def create_artifact(payload: ArtifactCreate, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    art = Artifact(
        title=payload.title,
        content_md=payload.content_md,
        owner_id=user.id,
        conversation_id=payload.conversation_id,
    )
    db.add(art)
    db.commit()
    db.refresh(art)
    version = ArtifactVersion(artifact_id=art.id, editor_id=user.id, content_md=art.content_md, status=art.status)
    db.add(version)
    db.commit()
    return _artifact_out(art)


@router.post("/{artifact_id}/versions")
def update_artifact(artifact_id: int, payload: ArtifactUpdate, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    art = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not art:
        raise HTTPException(404, "Artefact introuvable")
    art.content_md = payload.content_md
    art.status = payload.status
    db.add(ArtifactVersion(artifact_id=art.id, editor_id=user.id, content_md=payload.content_md, status=payload.status))
    db.commit()
    db.refresh(art)
    log_event(db, user.id, "artifact_iteration", {"artifact_id": art.id, "status": art.status})
    return _artifact_out(art)


@router.get("/{artifact_id}/versions")
def get_versions(artifact_id: int, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    versions = (
        db.query(ArtifactVersion)
        .filter(ArtifactVersion.artifact_id == artifact_id)
        .order_by(ArtifactVersion.created_at.desc())
        .all()
    )
    return [_version_out(v) for v in versions]


@router.get("")
def list_artifacts(db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    return [_artifact_out(a) for a in db.query(Artifact).all()]
