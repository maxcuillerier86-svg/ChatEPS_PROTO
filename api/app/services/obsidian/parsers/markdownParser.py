from __future__ import annotations

import hashlib
import re
from typing import Any

from app.services.obsidian.types import ObsidianChunk, ObsidianNote

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_INLINE_TAG_RE = re.compile(r"(?<!\w)#([\w\-/]+)")


def parse_markdown(note: ObsidianNote) -> dict[str, Any]:
    frontmatter, body = _split_frontmatter(note.content)
    title = _extract_title(body, note.title)
    headings = _extract_headings(body)
    links = _extract_links(body)
    tags = _extract_tags(frontmatter, body)
    return {
        "title": title,
        "frontmatter": frontmatter,
        "body": body,
        "headings": headings,
        "links": links,
        "tags": tags,
    }


def chunk_by_headings(note: ObsidianNote, parsed: dict[str, Any], max_chars: int = 1400, overlap: int = 180) -> list[ObsidianChunk]:
    body = parsed["body"]
    sections = _split_sections(body)
    if not sections:
        sections = [(None, body)]

    chunks: list[ObsidianChunk] = []
    idx = 0
    for heading, text in sections:
        txt = (text or "").strip()
        if not txt:
            continue
        for part in _token_chunk(txt, max_chars=max_chars, overlap=overlap):
            cid = _chunk_id(note.path, heading, idx, part)
            metadata = {
                "source": "obsidian",
                "filePath": note.path,
                "noteTitle": parsed.get("title") or note.title,
                "heading": heading,
                "tags": parsed.get("tags") or [],
                "outlinks": parsed.get("links", {}).get("outlinks") or [],
                "backlinks": parsed.get("links", {}).get("backlinks") or [],
                "frontmatter": parsed.get("frontmatter") or {},
            }
            chunks.append(
                ObsidianChunk(
                    id=cid,
                    text=part,
                    note_path=note.path,
                    note_title=parsed.get("title") or note.title,
                    heading=heading,
                    chunk_index=idx,
                    metadata=metadata,
                )
            )
            idx += 1
    return chunks


def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    raw = content[4:end]
    body = content[end + 5 :]
    frontmatter: dict[str, Any] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        frontmatter[k.strip()] = _parse_scalar(v.strip())
    return frontmatter, body


def _parse_scalar(v: str) -> Any:
    if v.startswith("[") and v.endswith("]"):
        items = [x.strip().strip('"\'') for x in v[1:-1].split(",") if x.strip()]
        return items
    if v.lower() in {"true", "false"}:
        return v.lower() == "true"
    return v.strip('"\'')


def _extract_title(body: str, fallback: str) -> str:
    for line in body.splitlines()[:20]:
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _extract_headings(body: str) -> list[str]:
    return [m.group(2).strip() for m in _HEADING_RE.finditer(body)]


def _extract_links(body: str) -> dict[str, list[str]]:
    links = [m.group(1).strip() for m in _WIKILINK_RE.finditer(body)]
    return {"outlinks": links, "backlinks": []}


def _extract_tags(frontmatter: dict[str, Any], body: str) -> list[str]:
    tags: set[str] = set()
    fm_tags = frontmatter.get("tags")
    if isinstance(fm_tags, list):
        tags.update(str(t).lstrip("#") for t in fm_tags)
    elif isinstance(fm_tags, str) and fm_tags:
        tags.add(fm_tags.lstrip("#"))
    tags.update(m.group(1).strip() for m in _INLINE_TAG_RE.finditer(body))
    return sorted({t for t in tags if t})


def _split_sections(body: str) -> list[tuple[str | None, str]]:
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        return []
    sections = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections.append((m.group(2).strip(), body[start:end]))
    return sections


def _token_chunk(text: str, max_chars: int = 1400, overlap: int = 180) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    out = []
    start = 0
    step = max(1, max_chars - overlap)
    while start < len(text):
        out.append(text[start : start + max_chars])
        start += step
    return [x for x in out if x.strip()]


def _chunk_id(path: str, heading: str | None, idx: int, text: str) -> str:
    raw = f"{path}|{heading}|{idx}|{text[:120]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
