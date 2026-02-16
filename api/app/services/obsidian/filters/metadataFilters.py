from __future__ import annotations

from datetime import datetime, timedelta, timezone


def apply_metadata_filters(chunks: list[dict], filters: dict | None) -> list[dict]:
    if not filters:
        return chunks

    tags = {t.lower() for t in (filters.get("tags") or [])}
    note_types = {t.lower() for t in (filters.get("noteType") or filters.get("note_types") or [])}
    course = (filters.get("course") or "").lower().strip()
    language = (filters.get("language") or "").lower().strip()
    recency_days = filters.get("recency_days")
    recency_cutoff = None
    if isinstance(recency_days, int) and recency_days > 0:
        recency_cutoff = datetime.now(timezone.utc) - timedelta(days=recency_days)

    out = []
    for ch in chunks:
        md = ch.get("metadata") or {}
        ctags = {str(t).lower() for t in (md.get("tags") or ch.get("tags") or [])}
        if tags and not (tags & ctags):
            continue

        ntype = str(md.get("noteType") or md.get("note_type") or ch.get("note_type") or "").lower()
        if note_types and ntype not in note_types:
            continue

        ccourse = str(md.get("course") or "").lower()
        if course and course != ccourse:
            continue

        clang = str(md.get("language") or "").lower()
        if language and language != clang:
            continue

        if recency_cutoff:
            modified = md.get("modified_at") or ch.get("modified_at")
            if modified:
                try:
                    dt = datetime.fromisoformat(str(modified).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < recency_cutoff:
                        continue
                except Exception:
                    pass
        out.append(ch)
    return out


def recency_boost(modified_at_iso: str | None) -> float:
    if not modified_at_iso:
        return 0.0
    try:
        dt = datetime.fromisoformat(str(modified_at_iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - dt).days)
        if age_days <= 7:
            return 0.25
        if age_days <= 30:
            return 0.12
    except Exception:
        return 0.0
    return 0.0
