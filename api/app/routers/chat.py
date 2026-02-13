import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.entities import Conversation, Message, User
from app.schemas.chat import ConversationCreate, MessageIn
from app.services.ollama import chat_stream
from app.services.rag import retrieve
from app.services.tracing import log_event

router = APIRouter(prefix="/chat", tags=["chat"])

MODE_SYSTEM = {
    "exploration_novice": "Tu es un co-créateur pédagogique en EPS. Explique clairement, pose micro-questions de compréhension, encourage la métacognition.",
    "co_design": "Tu aides à concevoir des plans de séance EPS complets avec objectifs, différenciation et évaluation.",
    "critique": "Tu critiques les propositions et suggères des itérations concrètes.",
    "justification": "Tu demandes les rationnels, alternatives et conditions d'application.",
    "evaluation_reflexive": "Tu mènes une évaluation réflexive. Termine chaque réponse par une auto-évaluation (1-5 + pourquoi).",
}


@router.post("/conversations")
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    conv = Conversation(title=payload.title, mode=payload.mode, type=payload.type, course_id=payload.course_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    log_event(db, user.id, "conversation_create", {"conversation_id": conv.id, "mode": conv.mode})
    return conv


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Conversation).order_by(Conversation.updated_at.desc()).all()


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()


@router.post("/conversations/{conversation_id}/stream")
async def stream_reply(conversation_id: int, payload: MessageIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(404, "Conversation introuvable")

    user_msg = Message(conversation_id=conv.id, user_id=user.id, role="user", content=payload.content)
    db.add(user_msg)
    db.commit()

    citations = []
    context = ""
    if payload.use_rag:
        hits = await retrieve(payload.content, payload.collection_ids)
        citations = [
            {"doc_id": h["doc_id"], "title": h["title"], "page": h["page"], "excerpt": h["text"][:280]}
            for h in hits
        ]
        context = "\n\nSources PDF:\n" + "\n".join([f"- {c['title']} p.{c['page']}: {c['excerpt']}" for c in citations])

    history = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.asc()).all()
    model_messages = [{"role": "system", "content": MODE_SYSTEM.get(conv.mode, MODE_SYSTEM["exploration_novice"])}]
    for m in history[-12:]:
        model_messages.append({"role": m.role, "content": m.content})
    model_messages[-1]["content"] = payload.content + context + "\nSi aucune source fournie, indique-le explicitement. Termine par auto-évaluation 1-5."

    async def event_stream():
        collected = ""
        async for line in chat_stream(model_messages):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            token = obj.get("message", {}).get("content", "")
            if token:
                collected += token
                yield f"data: {json.dumps({'token': token})}\n\n"
            if obj.get("done"):
                ai_msg = Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=collected,
                    metadata_json={"citations": citations},
                )
                db.add(ai_msg)
                db.commit()
                log_event(
                    db,
                    user.id,
                    "chat_turn",
                    {
                        "conversation_id": conv.id,
                        "has_citations": bool(citations),
                        "prompt_length": len(payload.content),
                        "mode": conv.mode,
                    },
                    conversation_id=conv.id,
                )
                yield f"data: {json.dumps({'done': True, 'citations': citations})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
