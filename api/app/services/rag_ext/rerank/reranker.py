from __future__ import annotations


def heuristic_rerank(query: str, items: list[dict], top_k: int = 8) -> list[dict]:
    q = (query or "").lower()
    q_terms = {t for t in q.split() if len(t) > 2}
    rescored = []
    for it in items:
        txt = (it.get("text") or "").lower()
        heading = (it.get("heading") or "").lower()
        tags = {str(t).lower() for t in (it.get("tags") or [])}
        overlap = len([t for t in q_terms if t in txt])
        heading_bonus = 0.2 if any(t in heading for t in q_terms) else 0.0
        tag_bonus = 0.1 if any(t in tags for t in q_terms) else 0.0
        score = float(it.get("fusion_score", it.get("score", 0.0))) + 0.03 * overlap + heading_bonus + tag_bonus
        obj = dict(it)
        obj["rerank_score"] = round(score, 4)
        rescored.append(obj)
    rescored.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return rescored[:top_k]
