import os
import re
from datetime import datetime
from pathlib import Path

from app.services.obsidian.types import ObsidianNote

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
_TAG_INLINE = re.compile(r"(?<!\w)#([\w\-_/]+)")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONTMATTER.match(text)
    if not m:
        return {}, text
    body = m.group(1)
    rest = text[m.end() :]
    data: dict[str, str | list[str]] = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        raw = v.strip()
        if raw.startswith("[") and raw.endswith("]"):
            items = [x.strip().strip('"\'') for x in raw[1:-1].split(",") if x.strip()]
            data[k] = items
        else:
            data[k] = raw.strip('"\'')
    return data, rest


def parse_markdown_note(path: Path, text: str) -> ObsidianNote:
    frontmatter, body = _parse_frontmatter(text)
    headings = [m.group(2).strip() for m in _HEADING.finditer(body)]
    wikilinks = [m.group(1).strip() for m in _WIKILINK.finditer(body)]

    title = frontmatter.get("title") if isinstance(frontmatter.get("title"), str) else None
    if not title:
        title = headings[0] if headings else path.stem

    tags = []
    fm_tags = frontmatter.get("tags")
    if isinstance(fm_tags, list):
        tags.extend([str(t).lstrip("#") for t in fm_tags])
    elif isinstance(fm_tags, str):
        tags.extend([t.strip().lstrip("#") for t in fm_tags.split(",") if t.strip()])
    tags.extend([t for t in _TAG_INLINE.findall(body)])
    tags = sorted({t for t in tags if t})

    st = path.stat() if path.exists() else None
    created_at = datetime.fromtimestamp(st.st_ctime) if st else None
    modified_at = datetime.fromtimestamp(st.st_mtime) if st else None

    return ObsidianNote(
        path=str(path),
        title=title,
        content=body,
        tags=tags,
        note_type=(frontmatter.get("type") or frontmatter.get("noteType") or _infer_type_from_path(path)),
        course=(frontmatter.get("course") if isinstance(frontmatter.get("course"), str) else None),
        status=(frontmatter.get("status") if isinstance(frontmatter.get("status"), str) else None),
        language=(frontmatter.get("language") if isinstance(frontmatter.get("language"), str) else None),
        headings=headings,
        wikilinks=wikilinks,
        created_at=created_at,
        modified_at=modified_at,
        frontmatter=frontmatter,
    )


def _infer_type_from_path(path: Path) -> str:
    folders = [p.lower() for p in path.parts]
    if any(x in folders for x in ["practice", "pratique", "seances"]):
        return "practice"
    if any(x in folders for x in ["reflection", "reflexion"]):
        return "reflection"
    if any(x in folders for x in ["artifacts", "artefacts", "rubrics"]):
        return "artifacts"
    return "theory"


def chunk_markdown_by_heading(note: ObsidianNote, chunk_size: int = 900) -> list[tuple[str | None, str]]:
    lines = note.content.splitlines()
    chunks: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    buff: list[str] = []

    def flush():
        nonlocal buff
        text = "\n".join(buff).strip()
        if not text:
            buff = []
            return
        if len(text) <= chunk_size:
            chunks.append((current_heading, text))
        else:
            for i in range(0, len(text), chunk_size):
                chunks.append((current_heading, text[i : i + chunk_size]))
        buff = []

    for ln in lines:
        m = _HEADING.match(ln)
        if m:
            flush()
            current_heading = m.group(2).strip()
            continue
        buff.append(ln)
    flush()

    if not chunks and note.content.strip():
        text = note.content.strip()
        for i in range(0, len(text), chunk_size):
            chunks.append((None, text[i : i + chunk_size]))
    return chunks


def safe_relpath(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return os.path.basename(str(path))
