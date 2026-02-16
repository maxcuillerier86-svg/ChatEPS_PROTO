from datetime import datetime, timedelta


def apply_obsidian_filters(chunks: list[dict], filters: dict | None) -> list[dict]:
    if not filters:
        return chunks

    tags = {t.lower() for t in (filters.get("tags") or [])}
    note_types = set(filters.get("noteType") or filters.get("note_type") or [])
    courses = set(filters.get("course") or [])
    recency_days = filters.get("recency_days")
    now = datetime.utcnow()

    out = []
    for c in chunks:
        if tags:
            ctags = {t.lower() for t in (c.get("tags") or [])}
            if not (ctags & tags):
                continue
        if note_types and c.get("note_type") not in note_types:
            continue
        if courses and c.get("course") not in courses:
            continue
        if recency_days:
            try:
                modified = datetime.fromisoformat((c.get("modified_at") or "").replace("Z", "+00:00")).replace(tzinfo=None)
                if modified < now - timedelta(days=int(recency_days)):
                    continue
            except Exception:
                pass
        out.append(c)
    return out
