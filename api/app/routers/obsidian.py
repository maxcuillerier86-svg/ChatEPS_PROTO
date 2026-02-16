from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.deps import get_actor_user
from app.models.entities import User
from app.services.obsidian.ObsidianClient import ObsidianClient
from app.services.obsidian.ObsidianSource import ObsidianConfig
from app.services.obsidian.formatters.obsidianMarkdown import format_obsidian_markdown
from app.services.obsidian_rag.ingestion.obsidianIngestor import get_status, incremental_obsidian_index

router = APIRouter(prefix="/obsidian", tags=["obsidian"])


def _split_csv(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def _normalize_target_folder(raw_folder: str | None, session_id: str, vault_path: str | None) -> str:
    default_folder = f"ChatEPS/{session_id}"
    folder = (raw_folder or "").strip()
    if not folder:
        return default_folder

    folder_posix = folder.replace("\\", "/").strip("/")
    abs_path = Path(folder).expanduser()
    vault = Path(vault_path).expanduser().resolve() if vault_path else None

    if abs_path.is_absolute() and vault:
        resolved = abs_path.resolve()
        if resolved == vault:
            return default_folder
        if vault in resolved.parents:
            rel = resolved.relative_to(vault)
            return str(rel).replace("\\", "/")
        raise ValueError("target_folder doit être dans le vault Obsidian ou être un chemin relatif")

    if folder_posix.startswith(".obsidian/") or folder_posix == ".obsidian":
        raise ValueError("target_folder interdit (.obsidian)")

    return folder_posix


def build_obsidian_config(payload: dict | None = None) -> ObsidianConfig:
    payload = payload or {}
    mode = payload.get("mode") or settings.obsidian_mode
    vault_path = payload.get("vault_path") or settings.obsidian_vault_path
    if mode == "filesystem" and vault_path:
        p = Path(vault_path).expanduser().resolve()
        vault_path = str(p)
    return ObsidianConfig(
        mode=mode,
        vault_path=vault_path,
        rest_api_base_url=payload.get("rest_api_base_url") or settings.obsidian_rest_api_base_url,
        api_key=payload.get("api_key") or settings.obsidian_api_key,
        included_folders=payload.get("included_folders") or _split_csv(settings.obsidian_included_folders),
        excluded_folders=payload.get("excluded_folders") or _split_csv(settings.obsidian_excluded_folders),
        excluded_patterns=payload.get("excluded_patterns") or _split_csv(settings.obsidian_excluded_patterns),
        max_notes_to_index=int(payload.get("max_notes_to_index") or settings.obsidian_max_notes_to_index),
        max_note_bytes=int(payload.get("max_note_bytes") or settings.obsidian_max_note_bytes),
        incremental_indexing=bool(payload.get("incremental_indexing", settings.obsidian_incremental_indexing)),
    )


@router.get("/status")
async def obsidian_status(user: User = Depends(get_actor_user)):
    cfg = build_obsidian_config()
    status = get_status()
    client = ObsidianClient(cfg)
    conn = await client.status()
    return {
        "config": {
            "mode": cfg.mode,
            "vault_path": cfg.vault_path,
            "rest_api_base_url": cfg.rest_api_base_url,
            "included_folders": cfg.included_folders,
            "excluded_folders": cfg.excluded_folders,
            "excluded_patterns": cfg.excluded_patterns,
            "max_notes_to_index": cfg.max_notes_to_index,
            "max_note_bytes": cfg.max_note_bytes,
            "incremental_indexing": cfg.incremental_indexing,
        },
        "index_status": status,
        "connection": conn,
    }


@router.post("/index")
async def obsidian_index(payload: dict | None = None, user: User = Depends(get_actor_user)):
    cfg = build_obsidian_config(payload)
    if cfg.mode == "filesystem":
        if not cfg.vault_path:
            raise HTTPException(
                status_code=400,
                detail="vault_path manquant (mode filesystem). Renseignez le chemin du vault Obsidian.",
            )
        vp = Path(cfg.vault_path).expanduser()
        if not vp.exists() or not vp.is_dir():
            raise HTTPException(status_code=400, detail=f"vault_path invalide ou inaccessible: {vp}")
    stats = await incremental_obsidian_index(cfg)
    return {"ok": True, "stats": stats.__dict__, "status": get_status()}


@router.post("/save")
async def obsidian_save(payload: dict, user: User = Depends(get_actor_user)):
    cfg = build_obsidian_config(payload.get("obsidian_config") if isinstance(payload, dict) else None)
    client = ObsidianClient(cfg)

    if not payload.get("answer"):
        raise HTTPException(status_code=400, detail="answer requis")

    session_id = str(payload.get("session_id") or "session")
    short_id = str(payload.get("short_id") or "msg")[:8]
    topic = str(payload.get("topic") or "knowledge")
    mode = str(payload.get("save_mode") or "manual-only")
    try:
        folder = _normalize_target_folder(payload.get("target_folder"), session_id, cfg.vault_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    note_name = client.default_note_name(topic, short_id)
    note_path = f"{folder}/{note_name}" if mode != "daily-note-append" else f"{folder}/{__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d')}.md"

    md = format_obsidian_markdown(
        question=str(payload.get("question") or ""),
        answer=str(payload.get("answer") or ""),
        session_id=session_id,
        conversation_id=int(payload.get("conversation_id") or 0),
        message_id=(int(payload.get("message_id")) if payload.get("message_id") is not None else None),
        model_name=payload.get("model_name"),
        student_level=payload.get("student_level"),
        confidence=payload.get("confidence"),
        sources=payload.get("sources") or [],
        learning_trace=payload.get("learning_trace") or {},
        rag_flags=payload.get("rag_flags") or {},
        include_sources=bool(payload.get("include_sources", True)),
        include_trace=bool(payload.get("include_trace", True)),
        include_retrieved_summary=bool(payload.get("include_retrieved_summary", False)),
    )

    status = await client.status()
    if status.get("active") == "none":
        raise HTTPException(
            status_code=400,
            detail="Aucun connecteur Obsidian actif. Vérifiez vault_path (filesystem) ou REST API (URL/API key).",
        )

    try:
        if mode == "daily-note-append":
            result = await client.append_note(note_path, md)
        else:
            result = await client.create_note(note_path, md)
            if not result.get("ok"):
                # append fallback if already exists/conflict
                result = await client.append_note(note_path, md)
        return {"ok": True, "saved": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Sauvegarde Obsidian refusée: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sauvegarde Obsidian échouée: {exc}")
