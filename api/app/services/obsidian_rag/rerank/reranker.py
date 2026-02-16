from datetime import datetime


def heuristic_rerank(query: str, hits: list[dict]) -> list[dict]:
    q = query.lower()
    for h in hits:
        boost = 0.0
        heading = (h.get("heading") or "").lower()
        if heading and any(tok in heading for tok in q.split()[:5]):
            boost += 0.08
        tags = [str(t).lower() for t in (h.get("tags") or [])]
        if any(tok in tags for tok in q.split()[:5]):
            boost += 0.06
        try:
            mod = h.get("modified_at")
            if mod:
                dt = datetime.fromisoformat(mod.replace("Z", "+00:00"))
                age_days = max(0.0, (datetime.utcnow() - dt.replace(tzinfo=None)).days)
                boost += max(0.0, 0.08 - min(age_days, 60) / 1000)
        except Exception:
            pass
        h["_fused_score"] = float(h.get("_fused_score", h.get("_score", 0.0))) + boost
    hits.sort(key=lambda x: x.get("_fused_score", 0.0), reverse=True)
    return hits
