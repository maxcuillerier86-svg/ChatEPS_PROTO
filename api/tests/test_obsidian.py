from app.services.obsidian.parsers.markdownParser import chunk_by_headings, parse_markdown
from app.services.obsidian.types import ObsidianNote


def test_markdown_parser_frontmatter_and_tags():
    note = ObsidianNote(
        path="Cours/Didactique.md",
        title="Didactique",
        content="""---
tags: [eps, didactique]
type: theory
---
# Didactique EPS
## Objectifs
Texte #pedagogie
[[LienNote]]
""",
    )
    parsed = parse_markdown(note)
    assert parsed["title"] == "Didactique EPS"
    assert "eps" in parsed["tags"]
    assert "pedagogie" in parsed["tags"]
    assert "LienNote" in parsed["links"]["outlinks"]


def test_chunk_by_headings():
    note = ObsidianNote(
        path="notes/test.md",
        title="test",
        content="# Titre\n## H1\nA" * 400,
    )
    parsed = parse_markdown(note)
    chunks = chunk_by_headings(note, parsed, max_chars=300, overlap=50)
    assert chunks
    assert all(c.note_path == "notes/test.md" for c in chunks)
