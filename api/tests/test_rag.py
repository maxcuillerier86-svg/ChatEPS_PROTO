from app.services.rag import chunk_text


def test_chunk_text():
    text = "abc " * 600
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
