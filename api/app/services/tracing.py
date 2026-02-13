from sqlalchemy.orm import Session

from app.models.entities import TraceEvent


def log_event(db: Session, user_id: int, event_type: str, payload: dict, conversation_id: int | None = None, score: float | None = None):
    event = TraceEvent(
        user_id=user_id,
        conversation_id=conversation_id,
        event_type=event_type,
        payload=payload,
        score=score,
    )
    db.add(event)
    db.commit()
