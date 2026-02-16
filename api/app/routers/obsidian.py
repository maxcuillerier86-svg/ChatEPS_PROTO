from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_actor_user
from app.models.entities import User
from app.services.obsidian.config_store import load_obsidian_config, save_obsidian_config
from app.services.obsidian.types import ObsidianConfig
from app.services.rag_ext.ingestion.obsidianIngestor import ObsidianIngestor, load_obsidian_manifest

router = APIRouter(prefix="/obsidian", tags=["obsidian"])


@router.get("/config")
def get_obsidian_config(user: User = Depends(get_actor_user)):
    cfg = load_obsidian_config()
    return {
        "mode": cfg.mode,
        "vault_path": cfg.vault_path,
        "rest_api_base_url": cfg.rest_api_base_url,
        "api_key_set": bool(cfg.api_key),
        "included_folders": cfg.included_folders,
        "excluded_folders": cfg.excluded_folders,
        "excluded_patterns": cfg.excluded_patterns,
        "max_notes_to_index": cfg.max_notes_to_index,
        "max_note_bytes": cfg.max_note_bytes,
        "default_metadata_filters": cfg.default_metadata_filters,
        "incremental_indexing": cfg.incremental_indexing,
        "vault_name": cfg.vault_name,
    }


@router.post("/config")
def set_obsidian_config(payload: dict, user: User = Depends(get_actor_user)):
    mode = payload.get("mode", "filesystem")
    if mode not in {"filesystem", "rest"}:
        raise HTTPException(status_code=400, detail="mode doit être filesystem ou rest")
    cfg = ObsidianConfig(
        mode=mode,
        vault_path=payload.get("vault_path"),
        rest_api_base_url=payload.get("rest_api_base_url"),
        api_key=payload.get("api_key"),
        included_folders=payload.get("included_folders") or [],
        excluded_folders=payload.get("excluded_folders") or [".obsidian", "templates", "attachments"],
        excluded_patterns=payload.get("excluded_patterns") or [".obsidian/**", "templates/**", "attachments/**"],
        max_notes_to_index=int(payload.get("max_notes_to_index", 5000)),
        max_note_bytes=int(payload.get("max_note_bytes", 400_000)),
        default_metadata_filters=payload.get("default_metadata_filters") or {},
        incremental_indexing=bool(payload.get("incremental_indexing", True)),
        vault_name=payload.get("vault_name") or "default",
    )
    save_obsidian_config(cfg)
    return {"ok": True}


@router.get("/status")
def obsidian_status(user: User = Depends(get_actor_user)):
    manifest = load_obsidian_manifest()
    files = manifest.get("files") or {}
    return {
        "last_run": manifest.get("last_run"),
        "notes_indexed": len(files),
        "chunks_indexed": sum(int(v.get("count", 0)) for v in files.values()),
    }


@router.post("/index")
async def run_obsidian_index(user: User = Depends(get_actor_user)):
    cfg = load_obsidian_config()
    if cfg.mode == "filesystem" and not cfg.vault_path:
        raise HTTPException(status_code=400, detail="OBSIDIAN_VAULT_PATH manquant")
    if cfg.mode == "rest" and (not cfg.rest_api_base_url or not cfg.api_key):
        raise HTTPException(status_code=400, detail="REST API base URL et API key requis")

    ingestor = ObsidianIngestor(cfg)
    result = await ingestor.run_incremental_index()
    return {"ok": True, **result}
