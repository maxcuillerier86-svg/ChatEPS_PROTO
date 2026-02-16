import re


def detect_obsidian_intents(text: str) -> dict:
    t = (text or "").lower()
    save = any(k in t for k in ["save to obsidian", "enregistre", "sauvegarde", "store", "keep", "record", "add to obsidian"])
    note_query = any(k in t for k in ["obsidian", "vault", "mes notes", "my notes", "according to my notes", "reflections"])
    open_note = any(k in t for k in ["open note", "ouvrir la note", "open in obsidian"])
    return {"save": save, "note_query": note_query, "open": open_note}


def is_canonical_knowledge(answer: str, user_text: str = "", teacher_marked: bool = False) -> bool:
    if teacher_marked:
        return True
    text = (answer or "")
    structured = any(h in text for h in ["#Plan", "#Checklist", "#Protocol", "#Template", "# Plan", "# Checklist"])
    user_save = any(k in (user_text or "").lower() for k in ["keep", "save", "record", "canonical", "store", "enregistre"])
    return structured or user_save


def extract_tool_calls(assistant_output: str) -> list[dict]:
    # Convention: <tool_call>{...json...}</tool_call>
    calls = []
    for m in re.finditer(r"<tool_call>(.*?)</tool_call>", assistant_output or "", re.DOTALL):
        raw = m.group(1).strip()
        try:
            import json

            obj = json.loads(raw)
            if isinstance(obj, dict) and obj.get("tool"):
                calls.append(obj)
        except Exception:
            continue
    return calls
