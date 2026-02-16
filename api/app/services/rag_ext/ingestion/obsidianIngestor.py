from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from qdrant_client.http.models import FieldCondition, Filter, MatchValue, PointStruct

from app.core.config import settings
from app.services.obsidian.ObsidianSource import ObsidianSource
from app.services.obsidian.parsers.markdownParser import chunk_by_headings, parse_markdown
from app.services.obsidian.types import ObsidianConfig
from app.services.ollama import embed_texts
from app.services.rag import ensure_collection, qdrant


class ObsidianIngestor:
    def __init__(self, cfg: ObsidianConfig):
        self.cfg = cfg
        root = Path(settings.storage_root)
        self.manifest_path = root / "obsidian_manifest.json"
        self.chunk_store = root / "obsidian_chunks"
        self.chunk_store.mkdir(parents=True, exist_ok=True)

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"files": {}, "config": {}, "last_run": None}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {"files": {}, "config": {}, "last_run": None}

    def _save_manifest(self, manifest: dict[str, Any]):
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def _note_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _note_cache_path(self, rel_path: str) -> Path:
        safe = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()
        return self.chunk_store / f"{safe}.json"

    async def run_incremental_index(self) -> dict[str, Any]:
        source = ObsidianSource(self.cfg)
        notes = await source.read_notes()
        manifest = self._load_manifest()
        files: dict[str, Any] = manifest.get("files") or {}

        seen_paths = set()
        indexed = 0
        updated = 0
        deleted = 0
        errors: list[str] = []

        for note in notes:
            seen_paths.add(note.path)
            note_hash = self._note_hash(note.content)
            prev = files.get(note.path) or {}
            modified_iso = note.modified_at.isoformat() if note.modified_at else None
            if self.cfg.incremental_indexing and prev.get("hash") == note_hash and prev.get("modified_at") == modified_iso:
                continue
            try:
                parsed = parse_markdown(note)
                chunks = chunk_by_headings(note, parsed)
                if not chunks:
                    continue
                vectors = await embed_texts([c.text for c in chunks])
                await ensure_collection(len(vectors[0]))

                # delete previous vectors for this note
                await self._delete_note_vectors(note.path)

                points = []
                for ch, vec in zip(chunks, vectors):
                    payload = {
                        "source": "obsidian",
                        "vaultName": self.cfg.vault_name,
                        "filePath": note.path,
                        "noteTitle": ch.note_title,
                        "heading": ch.heading,
                        "text": ch.text,
                        "doc_id": f"obs:{note.path}",
                        "title": ch.note_title,
                        "page": 1,
                        "tags": ch.metadata.get("tags") or [],
                        "note_type": (ch.metadata.get("frontmatter") or {}).get("type") or self._infer_note_type(note.path),
                        "modified_at": modified_iso,
                        "course": (ch.metadata.get("frontmatter") or {}).get("course"),
                        "language": (ch.metadata.get("frontmatter") or {}).get("language"),
                    }
                    points.append(PointStruct(id=ch.id, vector=vec, payload=payload))
                qdrant().upsert(collection_name=settings.qdrant_collection, points=points)

                # save chunk cache
                self._note_cache_path(note.path).write_text(
                    json.dumps([{"id": c.id, "text": c.text, "metadata": c.metadata, "heading": c.heading, "note_title": c.note_title, "note_path": c.note_path} for c in chunks], ensure_ascii=False),
                    encoding="utf-8",
                )

                files[note.path] = {
                    "hash": note_hash,
                    "modified_at": modified_iso,
                    "chunk_ids": [c.id for c in chunks],
                    "count": len(chunks),
                }
                indexed += len(chunks)
                updated += 1
            except Exception as exc:
                errors.append(f"{note.path}: {exc}")

        # deletions
        stale = [p for p in list(files.keys()) if p not in seen_paths]
        for path in stale:
            try:
                await self._delete_note_vectors(path)
                cpath = self._note_cache_path(path)
                if cpath.exists():
                    cpath.unlink()
                files.pop(path, None)
                deleted += 1
            except Exception as exc:
                errors.append(f"delete {path}: {exc}")

        manifest["files"] = files
        manifest["config"] = {
            "mode": self.cfg.mode,
            "vault_path": self.cfg.vault_path,
            "rest_api_base_url": self.cfg.rest_api_base_url,
            "included_folders": self.cfg.included_folders,
            "excluded_folders": self.cfg.excluded_folders,
        }
        manifest["last_run"] = __import__("datetime").datetime.utcnow().isoformat()
        self._save_manifest(manifest)
        return {
            "notes_seen": len(notes),
            "notes_updated": updated,
            "chunks_indexed": indexed,
            "notes_deleted": deleted,
            "errors": errors,
            "last_run": manifest["last_run"],
        }

    async def _delete_note_vectors(self, note_path: str):
        qdrant().delete(
            collection_name=settings.qdrant_collection,
            points_selector=Filter(must=[FieldCondition(key="filePath", match=MatchValue(value=note_path))]),
        )

    def _infer_note_type(self, path: str) -> str:
        p = path.lower()
        if "/reflection" in p or "reflection" in p:
            return "reflection"
        if "/artifacts" in p or "artifact" in p:
            return "artifacts"
        if "/practice" in p or "seance" in p or "séance" in p:
            return "practice"
        return "theory"


def load_obsidian_manifest() -> dict[str, Any]:
    path = Path(settings.storage_root) / "obsidian_manifest.json"
    if not path.exists():
        return {"files": {}, "last_run": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"files": {}, "last_run": None}
