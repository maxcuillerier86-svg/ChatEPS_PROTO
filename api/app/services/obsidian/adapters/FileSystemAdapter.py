from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.services.obsidian.types import ObsidianConfig, ObsidianNote


class FileSystemAdapter:
    def __init__(self, cfg: ObsidianConfig):
        self.cfg = cfg

    def discover_notes(self) -> list[Path]:
        if not self.cfg.vault_path:
            return []
        root = Path(self.cfg.vault_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            return []
        notes = []
        for p in root.rglob("*.md"):
            rel = p.relative_to(root).as_posix()
            if self._is_excluded(rel):
                continue
            if self.cfg.included_folders and not any(rel.startswith(f.strip("/") + "/") or rel == f.strip("/") for f in self.cfg.included_folders):
                continue
            notes.append(p)
            if len(notes) >= self.cfg.max_notes_to_index:
                break
        return notes

    def read_notes(self) -> list[ObsidianNote]:
        notes: list[ObsidianNote] = []
        root = Path(self.cfg.vault_path).expanduser().resolve()
        for p in self.discover_notes():
            data = p.read_bytes()
            if len(data) > self.cfg.max_note_bytes:
                continue
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError:
                content = data.decode("utf-8", errors="ignore")
            stat = p.stat()
            notes.append(
                ObsidianNote(
                    path=p.relative_to(root).as_posix(),
                    title=p.stem,
                    content=content,
                    metadata={},
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                    created_at=datetime.fromtimestamp(stat.st_ctime),
                )
            )
        return notes

    def _is_excluded(self, rel: str) -> bool:
        rel_lower = rel.lower()
        for part in self.cfg.excluded_folders:
            part = part.strip("/").lower()
            if not part:
                continue
            if rel_lower == part or rel_lower.startswith(part + "/"):
                return True
        # fallback lightweight pattern handling for **
        for patt in self.cfg.excluded_patterns:
            pp = patt.replace("**", "").strip("/").lower()
            if pp and rel_lower.startswith(pp):
                return True
        return False
