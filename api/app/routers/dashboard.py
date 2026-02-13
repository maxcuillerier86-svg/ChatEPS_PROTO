from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.entities import Consent, TraceEvent, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/me")
def my_progress(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    events = db.query(TraceEvent).filter(TraceEvent.user_id == user.id).all()
    counts = Counter([e.event_type for e in events])
    return {
        "timeline": [{"type": e.event_type, "at": e.created_at.isoformat(), "payload": e.payload} for e in events[-50:]],
        "metrics": {
            "iterations": counts.get("artifact_iteration", 0),
            "chat_turns": counts.get("chat_turn", 0),
            "source_usage": sum(1 for e in events if e.payload.get("has_citations")),
            "metacognition_prompts": counts.get("metacognition", 0),
        },
    }


@router.get("/cohort")
def cohort_progress(db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "admin"))):
    events = db.query(TraceEvent).all()
    by_user = {}
    for e in events:
        by_user.setdefault(e.user_id, {"chat_turns": 0, "iterations": 0, "citations": 0})
        if e.event_type == "chat_turn":
            by_user[e.user_id]["chat_turns"] += 1
            by_user[e.user_id]["citations"] += int(bool(e.payload.get("has_citations")))
        if e.event_type == "artifact_iteration":
            by_user[e.user_id]["iterations"] += 1
    return by_user


@router.post("/consent")
def set_consent(accepted: bool, details: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    consent = db.query(Consent).filter(Consent.user_id == user.id).first()
    if not consent:
        consent = Consent(user_id=user.id, accepted=accepted, details=details)
        db.add(consent)
    else:
        consent.accepted = accepted
        consent.details = details
    db.commit()
    return {"accepted": accepted}
