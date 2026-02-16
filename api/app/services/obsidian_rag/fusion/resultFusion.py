from typing import Any


def _norm(scores: list[float]) -> list[float]:
    if not scores:
        return []
    mn, mx = min(scores), max(scores)
    if mx - mn < 1e-8:
        return [1.0 for _ in scores]
    return [(s - mn) / (mx - mn) for s in scores]


def _key(it: dict[str, Any]) -> str:
    if it.get("source") == "obsidian":
        return f"obs:{it.get('file_path')}:{it.get('heading')}"
    return f"pdf:{it.get('doc_id')}:{it.get('page')}:{(it.get('text') or '')[:40]}"


def fuse_results(pdf_hits: list[dict], obsidian_hits: list[dict], top_k: int = 10) -> list[dict]:
    pdf_scores = _norm([float(h.get("_score", 0.0)) for h in pdf_hits])
    obs_scores = _norm([float(h.get("_score", 0.0)) for h in obsidian_hits])

    merged: dict[str, dict] = {}
    for h, s in zip(pdf_hits, pdf_scores):
        item = dict(h)
        item.setdefault("source", "pdf")
        item["_fused_score"] = 0.52 * s
        merged[_key(item)] = item

    for h, s in zip(obsidian_hits, obs_scores):
        item = dict(h)
        item.setdefault("source", "obsidian")
        item["_fused_score"] = max(item.get("_fused_score", 0.0), 0.48 * s)
        k = _key(item)
        if k in merged:
            merged[k]["_fused_score"] = max(merged[k]["_fused_score"], item["_fused_score"])
        else:
            merged[k] = item

    out = list(merged.values())
    out.sort(key=lambda x: x.get("_fused_score", 0.0), reverse=True)
    return out[:top_k]
