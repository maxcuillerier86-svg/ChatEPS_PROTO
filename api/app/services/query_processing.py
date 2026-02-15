from __future__ import annotations


def classify_intent(query: str, mode: str | None = None) -> str:
    q = (query or "").lower()
    if mode in {"evaluation_reflexive", "justification"}:
        return "reflection"
    if any(k in q for k in ["plan", "séance", "lesson", "co-design", "activité", "drill"]):
        return "lesson_design"
    if any(k in q for k in ["évaluer", "rubrique", "grille", "critère", "assessment"]):
        return "evaluation"
    if any(k in q for k in ["pourquoi", "justifie", "réflex", "métacognition", "retour"]):
        return "reflection"
    return "explanation"


def expand_query_semantically(query: str, intent: str) -> list[str]:
    q = query.strip()
    if not q:
        return []
    expansions = [
        f"{q} pédagogie EPS",
        f"{q} didactique éducation physique",
    ]
    by_intent = {
        "lesson_design": [f"{q} objectifs apprentissage consignes différenciation", f"{q} plan de leçon progression"],
        "evaluation": [f"{q} critères observables rubriques évaluation", f"{q} feedback formatif"],
        "reflection": [f"{q} justification choix pédagogiques", f"{q} métacognition pratique réflexive"],
        "explanation": [f"{q} concepts théoriques", f"{q} exemples application terrain"],
    }
    expansions.extend(by_intent.get(intent, []))
    # keep deterministic unique list
    out: list[str] = []
    seen = set()
    for e in expansions:
        s = e.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out[:4]


def build_student_context(student_level: str | None, confidence: int | None, pseudo: str | None = None) -> str:
    level = (student_level or "novice").strip().lower()
    level = level if level in {"novice", "intermédiaire", "expert"} else "novice"
    conf = confidence if isinstance(confidence, int) else None
    pieces = [f"Profil étudiant: {pseudo or 'inconnu'}", f"Niveau auto-déclaré: {level}"]
    if conf is not None:
        pieces.append(f"Confiance actuelle (1-5): {max(1, min(conf, 5))}")
    if level == "novice":
        pieces.append("Adapter les explications avec étapes concrètes et vérification de compréhension.")
    elif level == "intermédiaire":
        pieces.append("Fournir compromis pédagogiques et variantes contextualisées.")
    else:
        pieces.append("Privilégier analyse critique, nuances et arbitrages experts.")
    return " | ".join(pieces)
