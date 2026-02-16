from __future__ import annotations


def _normalize_scores(items: list[dict], key: str = "score") -> list[dict]:
    if not items:
        return []
    vals = [float(i.get(key, 0.0) or 0.0) for i in items]
    mn, mx = min(vals), max(vals)
    if mx - mn < 1e-9:
        for i in items:
            i["score_norm"] = 1.0
        return items
    for i, v in zip(items, vals):
        i["score_norm"] = (v - mn) / (mx - mn)
    return items


def fuse_results(pdf_hits: list[dict], artifact_hits: list[dict], obsidian_hits: list[dict], top_k: int = 10, prefer_obsidian: bool = False) -> list[dict]:
    pdf_hits = _normalize_scores(pdf_hits)
    artifact_hits = _normalize_scores(artifact_hits)
    obsidian_hits = _normalize_scores(obsidian_hits)

    merged = []
    for src, items, bias in [
        ("pdf", pdf_hits, 0.0),
        ("artifact", artifact_hits, 0.05),
        ("obsidian", obsidian_hits, 0.12 if prefer_obsidian else 0.0),
    ]:
        for it in items:
            row = dict(it)
            row["source"] = row.get("source") or src
            row["fusion_score"] = round(float(row.get("score_norm", row.get("score", 0.0))) + bias, 4)
            merged.append(row)

    merged.sort(key=lambda x: x.get("fusion_score", 0.0), reverse=True)

    # dedupe by source+doc+snippet prefix
    seen = set()
    out = []
    for m in merged:
        k = f"{m.get('source')}|{m.get('doc_id')}|{(m.get('text') or '')[:90]}"
        if k in seen:
            continue
        seen.add(k)
        out.append(m)
        if len(out) >= top_k:
            break
    return out
