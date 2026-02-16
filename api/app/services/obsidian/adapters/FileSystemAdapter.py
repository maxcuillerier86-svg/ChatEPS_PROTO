import fnmatch
import re
from pathlib import Path
from urllib.parse import quote


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
        self.root = Path(vault_path).expanduser().resolve() if vault_path else Path(".").resolve()
        self.included = included_folders or []
        self.excluded = excluded_folders or [".obsidian", "templates", "attachments"]
        self.patterns = excluded_patterns or [".obsidian/**", "templates/**", "attachments/**"]
        self.max_notes = max_notes_to_index
        self.max_bytes = max_note_bytes

    def is_ready(self) -> bool:
        return self.root.exists() and self.root.is_dir()

    def health(self) -> dict:
        return {"ok": self.is_ready(), "mode": "filesystem", "vault_path": str(self.root)}

    @staticmethod
    def sanitize_filename(name: str) -> str:
        x = re.sub(r"[\\/:*?\"<>|]", "-", (name or "").strip())
        x = re.sub(r"\s+", " ", x).strip().strip(".")
        return (x or "note")[:120]

    def _assert_inside(self, path: Path):
        rp = path.resolve()
        if self.root not in rp.parents and rp != self.root:
            raise ValueError("Path traversal bloqué")
        rel = str(rp.relative_to(self.root)).replace("\\", "/")
        if any(rel.startswith(ex.strip("/") + "/") or rel == ex.strip("/") for ex in self.excluded):
            raise ValueError("Chemin exclu")
        if any(fnmatch.fnmatch(rel, pat) for pat in self.patterns):
            raise ValueError("Chemin exclu")

    def _resolve_note_path(self, note_path: str) -> Path:
        cleaned = note_path.replace("\\", "/").lstrip("/")
        p = (self.root / cleaned).with_suffix(".md") if not cleaned.endswith(".md") else (self.root / cleaned)
        self._assert_inside(p)
        return p

    def list_notes(self) -> list[Path]:
        if not self.is_ready():
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

    def read_note(self, path: Path | str) -> str:
        rp = self._resolve_note_path(str(path)) if not isinstance(path, Path) else path.resolve()
        self._assert_inside(rp)
        return rp.read_text(encoding="utf-8", errors="ignore") if rp.exists() else ""

    def create_note(self, note_path: str, content: str) -> str:
        p = self._resolve_note_path(note_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            stem = self.sanitize_filename(p.stem)
            p = p.with_name(f"{stem}-new.md")
        p.write_text(content, encoding="utf-8")
        return str(p.relative_to(self.root)).replace("\\", "/")

    def append_to_note(self, note_path: str, content: str) -> str:
        p = self._resolve_note_path(note_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write("\n\n---\n\n")
            f.write(content)
        return str(p.relative_to(self.root)).replace("\\", "/")

    def search_notes(self, query: str, limit: int = 10) -> list[dict]:
        q = (query or "").lower().strip()
        if not q:
            return []
        out = []
        for p in self.list_notes():
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            idx = text.lower().find(q)
            if idx == -1:
                continue
            snippet = text[max(0, idx - 120) : idx + 220].replace("\n", " ")
            rel = str(p.relative_to(self.root)).replace("\\", "/")
            out.append({"path": rel, "title": p.stem, "snippet": snippet})
            if len(out) >= limit:
                break
        return out

    def open_uri(self, note_path: str) -> str:
        safe = quote(note_path.replace("\\", "/"))
        vault = quote(self.root.name)
        return f"obsidian://open?vault={vault}&file={safe}"
