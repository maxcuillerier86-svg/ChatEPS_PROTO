import fnmatch
from pathlib import Path


class FileSystemAdapter:
    def __init__(
        self,
        vault_path: str,
        included_folders: list[str] | None = None,
        excluded_folders: list[str] | None = None,
        excluded_patterns: list[str] | None = None,
        max_notes_to_index: int = 5000,
        max_note_bytes: int = 500_000,
    ):
        self.root = Path(vault_path).expanduser().resolve()
        self.included = included_folders or []
        self.excluded = excluded_folders or [".obsidian", "templates", "attachments"]
        self.patterns = excluded_patterns or [".obsidian/**", "templates/**", "attachments/**"]
        self.max_notes = max_notes_to_index
        self.max_bytes = max_note_bytes

    def list_notes(self) -> list[Path]:
        if not self.root.exists() or not self.root.is_dir():
            return []
        out: list[Path] = []
        for p in self.root.rglob("*.md"):
            rel = str(p.relative_to(self.root)).replace("\\", "/")
            if self.included and not any(rel.startswith(f.strip("/") + "/") or rel == f.strip("/") for f in self.included):
                continue
            if any(rel.startswith(ex.strip("/") + "/") for ex in self.excluded):
                continue
            if any(fnmatch.fnmatch(rel, pat) for pat in self.patterns):
                continue
            try:
                if p.stat().st_size > self.max_bytes:
                    continue
            except Exception:
                continue
            out.append(p)
            if len(out) >= self.max_notes:
                break
        return out

    def read_note(self, path: Path) -> str:
        rp = path.resolve()
        if self.root not in rp.parents and rp != self.root:
            raise ValueError("Path traversal bloqué")
        return rp.read_text(encoding="utf-8", errors="ignore")
