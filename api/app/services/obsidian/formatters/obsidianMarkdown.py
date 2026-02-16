from datetime import datetime


def format_obsidian_markdown(
    *,
    question: str,
    answer: str,
    session_id: str,
    conversation_id: int,
    message_id: int | None,
    model_name: str | None,
    student_level: str | None,
    confidence: int | None,
    sources: list[dict],
    learning_trace: dict | None,
    rag_flags: dict | None,
    include_sources: bool = True,
    include_trace: bool = True,
    include_retrieved_summary: bool = False,
) -> str:
    created = datetime.utcnow().isoformat()
    src_summary = [
        {
            "source": s.get("source"),
            "title": s.get("title"),
            "file_path": s.get("file_path"),
            "page": s.get("page"),
            "heading": s.get("heading"),
        }
        for s in sources
    ]
    fm = {
        "created_at": created,
        "session_id": session_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "model_name": model_name,
        "rag_flags": rag_flags or {},
        "student_level": student_level,
        "confidence": confidence,
        "sources_used": src_summary,
        "tags": ["ChatEPS", "EPS", "RAG", "Obsidian"],
    }

    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                if isinstance(item, dict):
                    lines.append("  -")
                    for ik, iv in item.items():
                        lines.append(f"      {ik}: {iv}")
                else:
                    lines.append(f"  - {item}")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for ik, iv in v.items():
                lines.append(f"  {ik}: {iv}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append("# Question")
    lines.append(question.strip())
    lines.append("")
    lines.append("# Answer (RAG)")
    lines.append(answer.strip())
    lines.append("")

    if include_sources:
        lines.append("# Sources / Citations")
        if sources:
            for s in sources:
                if s.get("source") == "obsidian":
                    lines.append(
                        f"- [Obsidian] {s.get('title') or s.get('file_path')} ({s.get('file_path')}#{s.get('heading') or 'section'})"
                    )
                else:
                    lines.append(f"- [PDF] {s.get('title')} (doc:{s.get('doc_id')} p.{s.get('page')})")
        else:
            lines.append("- Aucun")
        lines.append("")

    if include_trace:
        lines.append("# Learning trace")
        if learning_trace:
            for k, v in learning_trace.items():
                lines.append(f"- {k}: {v}")
        else:
            lines.append("- N/A")
        lines.append("")

    if include_retrieved_summary:
        lines.append("# Retrieved context summary")
        for s in sources[:8]:
            lines.append(f"- {s.get('source')}: {(s.get('excerpt') or '')[:180]}")
        lines.append("")

    lines.append("# Links")
    lines.append("- (Optionnel) Ajouter les liens internes Obsidian pertinents")
    return "\n".join(lines)
