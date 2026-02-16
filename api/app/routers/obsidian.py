from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.deps import get_actor_user
from app.models.entities import User
from app.services.obsidian.ObsidianSource import ObsidianConfig
from app.services.obsidian_rag.ingestion.obsidianIngestor import get_status, incremental_obsidian_index

router = APIRouter(prefix="/obsidian", tags=["obsidian"])


def _split_csv(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


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
def obsidian_status(user: User = Depends(get_actor_user)):
    cfg = build_obsidian_config()
    status = get_status()
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
    }


@router.post("/index")
async def obsidian_index(payload: dict | None = None, user: User = Depends(get_actor_user)):
    cfg = build_obsidian_config(payload)
    if cfg.mode == "filesystem" and (not cfg.vault_path or not Path(cfg.vault_path).exists()):
        raise HTTPException(status_code=400, detail="vault_path invalide ou inaccessible")
    stats = await incremental_obsidian_index(cfg)
    return {"ok": True, "stats": stats.__dict__, "status": get_status()}
