from pathlib import Path

from app.services.obsidian.parsers.markdownParser import chunk_markdown_by_heading, parse_markdown_note


def test_parse_markdown_frontmatter_and_tags(tmp_path: Path):
    md = """---
title: Didactique Volley
tags: [eps, volleyball]
type: practice
course: EPS101
---
# Intro
Texte #pedagogie
[[Note Liée]]
"""
    p = tmp_path / "note.md"
    p.write_text(md, encoding="utf-8")
    note = parse_markdown_note(p, md)
    assert note.title == "Didactique Volley"
    assert "eps" in note.tags
    assert note.note_type == "practice"
    assert note.course == "EPS101"
    assert note.wikilinks == ["Note Liée"]


def test_chunk_by_heading(tmp_path: Path):
    md = """# A
Contenu A
## B
Contenu B
"""
    p = tmp_path / "n.md"
    p.write_text(md, encoding="utf-8")
    note = parse_markdown_note(p, md)
    chunks = chunk_markdown_by_heading(note, chunk_size=20)
    assert len(chunks) >= 2
    assert any(h == "A" for h, _ in chunks)
