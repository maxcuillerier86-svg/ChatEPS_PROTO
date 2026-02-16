from app.services.query_processing import classify_intent, expand_query_semantically
from app.services.rag import chunk_text, compress_context, infer_doc_type, optimize_chunk_params


def test_chunk_text():
    text = "abc " * 600
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_query_intent_and_expansion():
    intent = classify_intent("Crée un plan de séance volleyball pour secondaire", mode="co_design")
    assert intent in {"lesson_design", "explanation"}
    expanded = expand_query_semantically("plan de séance volleyball", intent)
    assert len(expanded) >= 2


def test_doc_type_and_chunk_strategy():
    assert infer_doc_type("Grille d'évaluation formative", ["rubrique"]) == "artifacts"
    csize, overlap = optimize_chunk_params("x" * 5000, "practice")
    assert csize <= 700
    assert overlap >= 100


def test_context_compression():
    hits = [
        {
            "doc_id": 1,
            "title": "Doc A",
            "page": 2,
            "doc_type": "theory",
            "text": "Première phrase utile. Deuxième phrase utile. Troisième phrase longue.",
        },
        {
            "doc_id": 2,
            "title": "Doc B",
            "page": 4,
            "doc_type": "practice",
            "text": "Exercice pratique détaillé. Consigne et différenciation.",
        },
    ]
    compressed = compress_context(hits, max_chars=240)
    assert compressed
    assert all("excerpt" in c for c in compressed)
