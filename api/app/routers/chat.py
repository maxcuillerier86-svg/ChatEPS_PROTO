import json
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import get_actor_user
from app.models.entities import Conversation, Message, TraceEvent, User
from app.schemas.chat import ConversationCreate, MessageIn
from app.services.ollama import chat_stream, check_ollama, list_models, pull_model
from app.services.llm.tools.obsidianTools import execute_obsidian_tool, obsidian_tool_schemas
from app.services.query_processing import build_student_context, classify_intent, expand_query_semantically
from app.services.rag import compress_context, retrieve
from app.services.obsidian_rag.fusion.resultFusion import fuse_results
from app.services.obsidian_rag.rerank.reranker import heuristic_rerank
from app.services.obsidian_rag.retrieval.obsidianRetriever import retrieve_obsidian
from app.services.obsidian.ObsidianClient import ObsidianClient
from app.services.obsidian.ObsidianSource import ObsidianConfig
from app.services.obsidian.ObsidianRouter import detect_obsidian_intents, extract_tool_calls, is_canonical_knowledge
from app.services.tracing import log_event

router = APIRouter(prefix="/chat", tags=["chat"])

MODE_SYSTEM = {
    "exploration_novice": "Tu es un co-créateur pédagogique en EPS. Explique clairement, pose micro-questions de compréhension, encourage la métacognition.",
    "co_design": "Tu aides à concevoir des plans de séance EPS complets avec objectifs, différenciation et évaluation.",
    "critique": "Tu critiques les propositions et suggères des itérations concrètes.",
    "justification": "Tu demandes les rationnels, alternatives et conditions d'application.",
    "evaluation_reflexive": "Tu mènes une évaluation réflexive. Termine chaque réponse par une auto-évaluation (1-5 + pourquoi).",
}

GROUNDING_RULES = (
    "Mode ancrage strict: n'affirme rien qui ne soit pas supporté par les extraits fournis. "
    "Si la preuve est insuffisante, dis explicitement 'Sources insuffisantes'. "
    "Cite chaque affirmation clé au format [doc:ID p.PAGE]."
)


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


def _owned_conversation_ids(db: Session, user_id: int) -> set[int]:
    create_events = db.query(TraceEvent).filter(TraceEvent.user_id == user_id, TraceEvent.event_type == "conversation_create").all()
    return {int(e.payload.get("conversation_id")) for e in create_events if e.payload.get("conversation_id")}


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
    for did in selected_doc_ids:
        snippets = by_doc.get(int(did)) or []
        if snippets:
            out.append(snippets.pop(0))

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
    created_ids = list(_owned_conversation_ids(db, user.id))
    if not created_ids:
        return []
    conversations = db.query(Conversation).filter(Conversation.id.in_(created_ids)).order_by(Conversation.updated_at.desc()).all()
    return [_conversation_out(c) for c in conversations]


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    if conversation_id not in _owned_conversation_ids(db, user.id):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()
    return [_message_out(m) for m in messages]


@router.patch("/conversations/{conversation_id}")
def rename_conversation(conversation_id: int, payload: dict, db: Session = Depends(get_db), user: User = Depends(get_actor_user)):
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Nouveau titre requis")

    created_ids = _owned_conversation_ids(db, user.id)
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
    created_ids = _owned_conversation_ids(db, user.id)
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
    if conversation_id not in _owned_conversation_ids(db, user.id):
        raise HTTPException(status_code=404, detail="Conversation introuvable")

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

    intent = classify_intent(payload.content, conv_mode)
    expanded_queries = expand_query_semantically(payload.content, intent)
    student_context = build_student_context(payload.student_level, payload.confidence, pseudo=user_name)

    obs_intents = detect_obsidian_intents(payload.content)
    use_obsidian = bool(payload.use_obsidian or obs_intents.get("note_query"))

    citations: list[dict] = []
    context = ""
    retrieval_ms = 0.0

    if payload.use_rag and (payload.collection_ids or payload.metadata_filters or use_obsidian):
        t0 = perf_counter()
        try:
            target_k = max(8, len(payload.collection_ids or []) * 3)
            pdf_hits = await retrieve(
                payload.content,
                payload.collection_ids,
                top_k=target_k,
                expanded_queries=expanded_queries,
                intent=intent,
                metadata_filters=payload.metadata_filters,
            )
            pdf_hits = _diversify_hits(pdf_hits, payload.collection_ids, max_items=target_k)
            for h in pdf_hits:
                h.setdefault("source", "pdf")

            obsidian_hits = []
            if use_obsidian:
                try:
                    obsidian_hits = await retrieve_obsidian(
                        payload.content,
                        top_k=max(4, target_k // 2),
                        filters=payload.obsidian_filters,
                        prefer_obsidian=payload.prefer_obsidian,
                    )
                except Exception:
                    obsidian_hits = []

            merged_hits = fuse_results(pdf_hits, obsidian_hits, top_k=target_k)
            merged_hits = heuristic_rerank(payload.content, merged_hits)
            compressed = compress_context(merged_hits, max_chars=1800)
            citations = []
            for h in compressed:
                src = h.get("source") or ("obsidian" if h.get("file_path") else "pdf")
                citations.append(
                    {
                        "source": src,
                        "doc_id": h.get("doc_id"),
                        "title": h.get("title") or h.get("note_title"),
                        "page": h.get("page"),
                        "heading": h.get("heading"),
                        "file_path": h.get("file_path"),
                        "doc_type": h.get("doc_type") or h.get("note_type"),
                        "excerpt": (h.get("excerpt") or h.get("text") or "")[:280],
                        "score": round(float(h.get("_fused_score", h.get("_score", 0.0))), 4),
                    }
                )
            if citations:
                lines = []
                for c in citations:
                    if c["source"] == "obsidian":
                        lines.append(
                            f"- [obsidian:{c.get('file_path')}#{c.get('heading') or 'section'}] ({c.get('doc_type','note')}) {c.get('title')}: {c.get('excerpt')}"
                        )
                    else:
                        lines.append(
                            f"- [pdf:doc:{c.get('doc_id')} p.{c.get('page')}] ({c.get('doc_type','theory')}) {c.get('title')}: {c.get('excerpt')}"
                        )
                context = "\n\nSources récupérées (PDF + Obsidian):\n" + "\n".join(lines)
            elif payload.strict_grounding:
                context = "\n\nSources insuffisantes pour ancrage strict."
        except Exception:
            context = "\n\nNote: RAG indisponible (index/embeddings). Réponse sans sources pour ce tour."
        retrieval_ms = (perf_counter() - t0) * 1000

    history = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at.asc()).all()
    system_prompt = MODE_SYSTEM.get(conv_mode, MODE_SYSTEM["exploration_novice"])
    if payload.strict_grounding:
        system_prompt = f"{system_prompt}\n{GROUNDING_RULES}"

    model_messages = [{"role": "system", "content": system_prompt}]
    for m in history[-12:]:
        model_messages.append({"role": m.role, "content": m.content})

    final_user_prompt = payload.content
    final_user_prompt += f"\n\nContexte étudiant: {student_context}"
    final_user_prompt += f"\nIntent détecté: {intent}."
    if expanded_queries:
        final_user_prompt += f"\nRequêtes d'expansion: {', '.join(expanded_queries)}"
    final_user_prompt += context
    final_user_prompt += "\nRespecte strictement les citations quand des sources sont fournies, et distingue clairement Obsidian vs PDF."
    final_user_prompt += "\nSi une opération Obsidian est requise, génère exclusivement un bloc <tool_call>{\"tool\":\"obsidian.search|obsidian.write|obsidian.append|obsidian.open|obsidian.status\",\"args\":{...}}</tool_call>. Ne fabrique aucune action de fichier hors tool call."
    if payload.strict_grounding:
        final_user_prompt += " Si les preuves manquent, réponds uniquement 'Sources insuffisantes'."
    final_user_prompt += " Termine par auto-évaluation 1-5."
    model_messages[-1]["content"] = final_user_prompt

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
                    output_text = collected
                    if payload.strict_grounding and payload.use_rag and not citations:
                        output_text = "Sources insuffisantes pour répondre de manière ancrée sur les PDF sélectionnés."

                    tool_results = []
                    try:
                        obs_cfg = ObsidianConfig(
                            mode=settings.obsidian_mode,
                            vault_path=settings.obsidian_vault_path,
                            rest_api_base_url=settings.obsidian_rest_api_base_url,
                            api_key=settings.obsidian_api_key,
                            included_folders=[x.strip() for x in settings.obsidian_included_folders.split(",") if x.strip()],
                            excluded_folders=[x.strip() for x in settings.obsidian_excluded_folders.split(",") if x.strip()],
                            excluded_patterns=[x.strip() for x in settings.obsidian_excluded_patterns.split(",") if x.strip()],
                            max_notes_to_index=settings.obsidian_max_notes_to_index,
                            max_note_bytes=settings.obsidian_max_note_bytes,
                            incremental_indexing=settings.obsidian_incremental_indexing,
                        )
                        obs_client = ObsidianClient(obs_cfg)
                        for call in extract_tool_calls(output_text):
                            tool_results.append(await execute_obsidian_tool(obs_client, call))
                    except Exception:
                        tool_results = []

                    save_mode = payload.obsidian_save_mode or "manual-only"
                    should_autosave = bool(payload.autosave_to_obsidian and save_mode != "manual-only")
                    if save_mode == "canonical-only":
                        should_autosave = should_autosave and is_canonical_knowledge(output_text, payload.content, payload.mark_canonical)
                    if obs_intents.get("save"):
                        should_autosave = True

                    obsidian_save = None
                    if should_autosave:
                        try:
                            obs_cfg = ObsidianConfig(
                            mode=settings.obsidian_mode,
                            vault_path=settings.obsidian_vault_path,
                            rest_api_base_url=settings.obsidian_rest_api_base_url,
                            api_key=settings.obsidian_api_key,
                            included_folders=[x.strip() for x in settings.obsidian_included_folders.split(",") if x.strip()],
                            excluded_folders=[x.strip() for x in settings.obsidian_excluded_folders.split(",") if x.strip()],
                            excluded_patterns=[x.strip() for x in settings.obsidian_excluded_patterns.split(",") if x.strip()],
                            max_notes_to_index=settings.obsidian_max_notes_to_index,
                            max_note_bytes=settings.obsidian_max_note_bytes,
                            incremental_indexing=settings.obsidian_incremental_indexing,
                        )
                            obs_client = ObsidianClient(obs_cfg)
                            save_payload = {
                                "session_id": f"conv-{conv_id}",
                                "short_id": f"m{conv_id}",
                                "topic": conv_mode,
                                "save_mode": save_mode,
                                "target_folder": payload.obsidian_target_folder or f"ChatEPS/{conv_id}",
                                "question": payload.content,
                                "answer": output_text,
                                "conversation_id": conv_id,
                                "model_name": payload.model,
                                "student_level": payload.student_level,
                                "confidence": payload.confidence,
                                "sources": citations,
                                "learning_trace": {
                                    "intent": intent,
                                    "ai_influence": "high" if len(citations) > 1 else "medium",
                                },
                                "rag_flags": {"grounding_strict": payload.strict_grounding, "top_k": len(citations)},
                                "include_sources": payload.include_sources_in_save,
                                "include_trace": payload.include_trace_in_save,
                                "include_retrieved_summary": payload.include_retrieved_summary_in_save,
                            }
                            # inline save
                            from app.services.obsidian.formatters.obsidianMarkdown import format_obsidian_markdown
                            note_name = obs_client.default_note_name(save_payload["topic"], save_payload["short_id"])
                            note_path = f"{save_payload['target_folder'].strip('/')}/{note_name}" if save_mode != "daily-note-append" else f"{save_payload['target_folder'].strip('/')}/{__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d')}.md"
                            md = format_obsidian_markdown(
                                question=save_payload["question"],
                                answer=save_payload["answer"],
                                session_id=save_payload["session_id"],
                                conversation_id=save_payload["conversation_id"],
                                message_id=None,
                                model_name=save_payload["model_name"],
                                student_level=save_payload["student_level"],
                                confidence=save_payload["confidence"],
                                sources=save_payload["sources"],
                                learning_trace=save_payload["learning_trace"],
                                rag_flags=save_payload["rag_flags"],
                                include_sources=save_payload["include_sources"],
                                include_trace=save_payload["include_trace"],
                                include_retrieved_summary=save_payload["include_retrieved_summary"],
                            )
                            obsidian_save = await (obs_client.append_note(note_path, md) if save_mode == "daily-note-append" else obs_client.create_note(note_path, md))
                        except Exception:
                            obsidian_save = {"ok": False}

                    with SessionLocal() as writer_db:
                        ai_msg = Message(
                            conversation_id=conv_id,
                            role="assistant",
                            content=output_text,
                            metadata_json={
                                "citations": citations,
                                "model": payload.model,
                                "intent": intent,
                                "expanded_queries": expanded_queries,
                                "strict_grounding": payload.strict_grounding,
                                "retrieval_ms": round(retrieval_ms, 2),
                                "source_counts": {"pdf": len([c for c in citations if c.get("source") == "pdf"]), "obsidian": len([c for c in citations if c.get("source") == "obsidian"])},
                                "tool_results": tool_results,
                                "obsidian_save": obsidian_save,
                                "available_tools": [t.get("name") for t in obsidian_tool_schemas()],
                            },
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
                                "intent": intent,
                                "retrieval_ms": round(retrieval_ms, 2),
                                "source_counts": {"pdf": len([c for c in citations if c.get("source") == "pdf"]), "obsidian": len([c for c in citations if c.get("source") == "obsidian"])},
                                "tool_results": tool_results,
                                "obsidian_save": obsidian_save,
                                "available_tools": [t.get("name") for t in obsidian_tool_schemas()],
                            },
                            conversation_id=conv_id,
                        )
                    yield f"data: {json.dumps({'done': True, 'citations': citations, 'tool_results': tool_results, 'obsidian_save': obsidian_save})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': f'Échec chat Ollama: {exc}'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
