from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.services.obsidian.types import ObsidianConfig


def _cfg_path() -> Path:
    p = Path(settings.storage_root)
    p.mkdir(parents=True, exist_ok=True)
    return p / "obsidian_config.json"


def load_obsidian_config() -> ObsidianConfig:
    path = _cfg_path()
    if not path.exists():
        return ObsidianConfig(vault_path=settings.obsidian_vault_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ObsidianConfig(
            mode=data.get("mode", "filesystem"),
            vault_path=data.get("vault_path") or settings.obsidian_vault_path,
            rest_api_base_url=data.get("rest_api_base_url") or settings.obsidian_rest_api_base_url,
            api_key=data.get("api_key") or settings.obsidian_api_key,
            included_folders=data.get("included_folders") or [],
            excluded_folders=data.get("excluded_folders") or [".obsidian", "templates", "attachments"],
            excluded_patterns=data.get("excluded_patterns") or [".obsidian/**", "templates/**", "attachments/**"],
            max_notes_to_index=int(data.get("max_notes_to_index", 5000)),
            max_note_bytes=int(data.get("max_note_bytes", 400_000)),
            default_metadata_filters=data.get("default_metadata_filters") or {},
            incremental_indexing=bool(data.get("incremental_indexing", True)),
            vault_name=data.get("vault_name") or "default",
        )
    except Exception:
        return ObsidianConfig(vault_path=settings.obsidian_vault_path)


def save_obsidian_config(cfg: ObsidianConfig):
    data = {
        "mode": cfg.mode,
        "vault_path": cfg.vault_path,
        "rest_api_base_url": cfg.rest_api_base_url,
        "api_key": cfg.api_key,
        "included_folders": cfg.included_folders,
        "excluded_folders": cfg.excluded_folders,
        "excluded_patterns": cfg.excluded_patterns,
        "max_notes_to_index": cfg.max_notes_to_index,
        "max_note_bytes": cfg.max_note_bytes,
        "default_metadata_filters": cfg.default_metadata_filters,
        "incremental_indexing": cfg.incremental_indexing,
        "vault_name": cfg.vault_name,
    }
    _cfg_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
