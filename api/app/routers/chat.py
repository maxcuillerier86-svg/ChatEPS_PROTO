import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.deps import get_actor_user
from app.models.entities import Conversation, Message, TraceEvent, User
from app.schemas.chat import ConversationCreate, MessageIn
from app.services.ollama import chat_stream, check_ollama, list_models, pull_model
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


def _conversation_out(conv: Conversation) -> dict:
    return {
        "id": conv.id,
        "title": conv.title,
        "mode": conv.mode,
        "type": conv.type,
        "course_id": conv.course_id,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
    }


def _message_out(msg: Message) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "role": msg.role,
        "content": msg.content,
        "metadata_json": msg.metadata_json,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def _diversify_hits(hits: list[dict], selected_doc_ids: list[int] | None, max_items: int) -> list[dict]:
    if not hits:
        return []
    if not selected_doc_ids or len(selected_doc_ids) <= 1:
        return hits[:max_items]

    by_doc: dict[int, list[dict]] = {}
    for h in hits:
        did = int(h.get("doc_id", -1))
        by_doc.setdefault(did, []).append(h)

    out: list[dict] = []
    # one snippet per selected doc first
    for did in selected_doc_ids:
        snippets = by_doc.get(int(did)) or []
        if snippets:
            out.append(snippets.pop(0))
    # then fill with remaining best hits
    if len(out) < max_items:
        for h in hits:
            if h not in out:
                out.append(h)
            if len(out) >= max_items:
                break
    return out[:max_items]


@router.get("/models")
async def models():
    return {"models": await list_models()}


@router.post("/models/pull")
async def pull_chat_model(payload: dict):
    model = (payload.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="Nom de modèle requis")
    try:
        result = await pull_model(model)
        return {"ok": True, "model": model, "result": result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Échec pull modèle: {exc}")


@router.post("/conversations")
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    conv = Conversation(title=payload.title, mode=payload.mode, type=payload.type, course_id=payload.course_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    log_event(db, user.id, "conversation_create", {"conversation_id": conv.id, "mode": conv.mode, "pseudo": user.full_name})
    return _conversation_out(conv)


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    created_ids = [
        int(e.payload.get("conversation_id"))
        for e in db.query(TraceEvent).filter(TraceEvent.user_id == user.id, TraceEvent.event_type == "conversation_create").all()
        if e.payload.get("conversation_id")
    ]
    if not created_ids:
        return []
    conversations = db.query(Conversation).filter(Conversation.id.in_(created_ids)).order_by(Conversation.updated_at.desc()).all()
    return [_conversation_out(c) for c in conversations]


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()
    return [_message_out(m) for m in messages]






@router.patch("/conversations/{conversation_id}")
def rename_conversation(conversation_id: int, payload: dict, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Nouveau titre requis")

    create_events = db.query(TraceEvent).filter(
        TraceEvent.user_id == user.id,
        TraceEvent.event_type == "conversation_create",
    ).all()
    created_ids = {int(e.payload.get("conversation_id")) for e in create_events if e.payload.get("conversation_id")}
    if conversation_id not in created_ids:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    conv.title = title
    db.commit()
    db.refresh(conv)
    log_event(db, user.id, "conversation_rename", {"conversation_id": conversation_id, "title": title, "pseudo": user.full_name})
    return _conversation_out(conv)
@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    create_events = db.query(TraceEvent).filter(
        TraceEvent.user_id == user.id,
        TraceEvent.event_type == "conversation_create",
    ).all()
    created_ids = {int(e.payload.get("conversation_id")) for e in create_events if e.payload.get("conversation_id")}
    if conversation_id not in created_ids:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    db.query(Message).filter(Message.conversation_id == conversation_id).delete(synchronize_session=False)
    db.query(TraceEvent).filter(TraceEvent.user_id == user.id, TraceEvent.conversation_id == conversation_id).delete(synchronize_session=False)
    db.delete(conv)
    db.commit()

    log_event(db, user.id, "conversation_delete", {"conversation_id": conversation_id, "pseudo": user.full_name})
    return {"ok": True}
@router.post("/conversations/{conversation_id}/stream")
async def stream_reply(conversation_id: int, payload: MessageIn, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(404, "Conversation introuvable")

    conv_id = int(conv.id)
    conv_mode = str(conv.mode)
    user_id = int(user.id)
    user_name = str(user.full_name)

    ok, err = await check_ollama()
    if not ok:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama inaccessible ({err}). Définissez OLLAMA_URL=http://localhost:11434 en local.",
        )

    user_msg = Message(conversation_id=conv_id, user_id=user_id, role="user", content=payload.content)
    db.add(user_msg)
    db.commit()

    citations = []
    context = ""
    if payload.use_rag:
        try:
            target_k = max(6, len(payload.collection_ids or []) * 2)
            hits = await retrieve(payload.content, payload.collection_ids, top_k=target_k)
            hits = _diversify_hits(hits, payload.collection_ids, max_items=target_k)
            citations = [
                {"doc_id": h["doc_id"], "title": h["title"], "page": h["page"], "excerpt": h["text"][:280]}
                for h in hits
            ]
            context = "\n\nSources PDF:\n" + "\n".join([f"- {c['title']} p.{c['page']}: {c['excerpt']}" for c in citations])
        except Exception:
            context = "\n\nNote: RAG indisponible (index/embeddings). Réponse sans sources PDF pour ce tour."

    history = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at.asc()).all()
    model_messages = [{"role": "system", "content": MODE_SYSTEM.get(conv_mode, MODE_SYSTEM["exploration_novice"])}]
    for m in history[-12:]:
        model_messages.append({"role": m.role, "content": m.content})
    model_messages[-1]["content"] = payload.content + context + "\nSi plusieurs sources PDF sont sélectionnées, compare-les explicitement. Si aucune source fournie, indique-le explicitement. Termine par auto-évaluation 1-5."

    async def event_stream():
        collected = ""
        try:
            async for line in chat_stream(model_messages, model=payload.model):
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = obj.get("message", {}).get("content", "")
                if token:
                    collected += token
                    yield f"data: {json.dumps({'token': token})}\n\n"
                if obj.get("done"):
                    with SessionLocal() as writer_db:
                        ai_msg = Message(
                            conversation_id=conv_id,
                            role="assistant",
                            content=collected,
                            metadata_json={"citations": citations, "model": payload.model},
                        )
                        writer_db.add(ai_msg)
                        writer_db.commit()
                        log_event(
                            writer_db,
                            user_id,
                            "chat_turn",
                            {
                                "conversation_id": conv_id,
                                "has_citations": bool(citations),
                                "prompt_length": len(payload.content),
                                "mode": conv_mode,
                                "model": payload.model,
                                "pseudo": user_name,
                            },
                            conversation_id=conv_id,
                        )
                    yield f"data: {json.dumps({'done': True, 'citations': citations})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': f'Échec chat Ollama: {exc}'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
