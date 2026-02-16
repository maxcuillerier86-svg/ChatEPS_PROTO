import hashlib
import json
import uuid
from dataclasses import asdict
from pathlib import Path

from qdrant_client.http.models import FieldCondition, Filter, MatchValue, PointStruct

from app.core.config import settings
from app.services.obsidian.ObsidianSource import ObsidianConfig, ObsidianSource
from app.services.obsidian.parsers.markdownParser import chunk_markdown_by_heading, parse_markdown_note, safe_relpath
from app.services.obsidian.types import ObsidianIngestStats
from app.services.ollama import embed_texts
from app.services.rag import qdrant


def _manifest_path() -> Path:
    p = Path(settings.storage_root) / "obsidian"
    p.mkdir(parents=True, exist_ok=True)
    return p / "manifest.json"


def _status_path() -> Path:
    p = Path(settings.storage_root) / "obsidian"
    p.mkdir(parents=True, exist_ok=True)
    return p / "status.json"


def load_manifest() -> dict:
    p = _manifest_path()
    if not p.exists():
        return {"files": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"files": {}}


def save_manifest(manifest: dict):
    _manifest_path().write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def save_status(status: dict):
    _status_path().write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def get_status() -> dict:
    p = _status_path()
    if not p.exists():
        return {"last_run": None, "indexed": 0, "errors": 0, "deleted": 0, "mode": None}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"last_run": None, "indexed": 0, "errors": 0, "deleted": 0, "mode": None}


def file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()


def _chunk_point_id(file_key: str, i: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"obsidian:{file_key}:{i}"))


async def incremental_obsidian_index(config: ObsidianConfig) -> ObsidianIngestStats:
    stats = ObsidianIngestStats()
    source = ObsidianSource(config)

    manifest = load_manifest()
    files_meta: dict = manifest.setdefault("files", {})

    notes = await source.list_notes()
    current_keys = set(notes)

    # deletions
    removed = [k for k in list(files_meta.keys()) if k not in current_keys]
    for path in removed:
        info = files_meta.get(path, {})
        for pid in info.get("chunk_ids", []):
            try:
                qdrant().delete(
                    collection_name=settings.qdrant_collection,
                    points_selector=[pid],
                )
            except Exception:
                pass
        files_meta.pop(path, None)
        stats.deleted += 1

    for path in notes:
        try:
            content = await source.read_note(path)
            if not content.strip():
                stats.skipped += 1
                continue
            h = file_hash(content)
            prev = files_meta.get(path)
            if config.incremental_indexing and prev and prev.get("hash") == h:
                stats.skipped += 1
                continue

            note = parse_markdown_note(Path(path), content)
            sections = chunk_markdown_by_heading(note)
            texts = [txt for _, txt in sections if txt.strip()]
            if not texts:
                stats.skipped += 1
                continue

            vectors = await embed_texts(texts)
            chunk_ids: list[str] = []
            points = []
            for i, ((heading, txt), vec) in enumerate(zip(sections, vectors)):
                pid = _chunk_point_id(path, i)
                rel = safe_relpath(Path(path), Path(config.vault_path).expanduser().resolve()) if config.vault_path else path
                chunk_ids.append(pid)
                points.append(
                    PointStruct(
                        id=pid,
                        vector=vec,
                        payload={
                            "source": "obsidian",
                            "vault": (Path(config.vault_path).name if config.vault_path else "rest-vault"),
                            "file_path": rel,
                            "note_title": note.title,
                            "heading": heading,
                            "text": txt,
                            "tags": note.tags,
                            "note_type": note.note_type,
                            "course": note.course,
                            "status": note.status,
                            "language": note.language,
                            "modified_at": note.modified_at.isoformat() if note.modified_at else None,
                            "wikilinks": note.wikilinks,
                        },
                    )
                )
            if points:
                qdrant().upsert(collection_name=settings.qdrant_collection, points=points)

            files_meta[path] = {
                "hash": h,
                "chunk_ids": chunk_ids,
                "modified_at": note.modified_at.isoformat() if note.modified_at else None,
                "note": asdict(note) | {"content": None},
            }
            stats.indexed += 1
        except Exception:
            stats.errors += 1

    save_manifest(manifest)
    save_status(
        {
            "last_run": __import__("datetime").datetime.utcnow().isoformat(),
            "indexed": stats.indexed,
            "skipped": stats.skipped,
            "deleted": stats.deleted,
            "errors": stats.errors,
            "mode": config.mode,
        }
    )
    return stats
