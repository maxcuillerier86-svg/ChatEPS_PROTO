from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.obsidian.ObsidianClient import ObsidianClient
from app.services.obsidian.ObsidianSource import ObsidianConfig
from app.services.obsidian.adapters.FileSystemAdapter import FileSystemAdapter
from app.services.obsidian.formatters.obsidianMarkdown import format_obsidian_markdown

client = TestClient(app)


def test_filename_sanitization():
    x = FileSystemAdapter.sanitize_filename('Plan: Volley/Session*1?')
    assert ':' not in x and '/' not in x and '*' not in x and '?' not in x


def test_markdown_formatter_has_frontmatter_and_sections():
    md = format_obsidian_markdown(
        question='Q',
        answer='A',
        session_id='s1',
        conversation_id=1,
        message_id=2,
        model_name='llama',
        student_level='novice',
        confidence=3,
        sources=[{'source': 'pdf', 'title': 'Doc', 'doc_id': 1, 'page': 2}],
        learning_trace={'change': 'x'},
        rag_flags={'grounding_strict': True},
    )
    assert md.startswith('---')
    assert '# Question' in md and '# Answer (RAG)' in md and '# Sources / Citations' in md


def test_adapter_selection_fallback(tmp_path):
    import asyncio

    cfg = ObsidianConfig(mode='rest', vault_path=str(tmp_path), rest_api_base_url='http://127.0.0.1:9', api_key='x')
    c = ObsidianClient(cfg)
    st = asyncio.run(c.status())
    assert st['active'] in {'filesystem', 'rest', 'none'}


def test_filesystem_adapter_accepts_absolute_path_inside_vault(tmp_path):
    adapter = FileSystemAdapter(str(tmp_path))
    inside = tmp_path / "ChatEPS" / "note-a.md"
    resolved = adapter._resolve_note_path(str(inside))
    assert resolved == inside


def test_filesystem_adapter_rejects_absolute_path_outside_vault(tmp_path):
    adapter = FileSystemAdapter(str(tmp_path))
    outside = Path("/tmp/outside-note.md")
    try:
        adapter._resolve_note_path(str(outside))
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "Path traversal" in str(exc)


def test_obsidian_save_returns_400_for_invalid_target_folder(tmp_path):
    prev_mode, prev_vault = settings.obsidian_mode, settings.obsidian_vault_path
    settings.obsidian_mode = "filesystem"
    settings.obsidian_vault_path = str(tmp_path)
    try:
        r = client.post(
            "/obsidian/save",
            headers={"X-Pseudo": "ObsidianTest"},
            json={
                "answer": "réponse",
                "target_folder": "/tmp/not-allowed",
                "obsidian_config": {"mode": "filesystem", "vault_path": str(tmp_path)},
            },
        )
        assert r.status_code == 400
        assert "target_folder" in r.json()["detail"]
    finally:
        settings.obsidian_mode, settings.obsidian_vault_path = prev_mode, prev_vault
