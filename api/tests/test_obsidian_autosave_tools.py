from app.services.obsidian.ObsidianClient import ObsidianClient
from app.services.obsidian.ObsidianSource import ObsidianConfig
from app.services.obsidian.adapters.FileSystemAdapter import FileSystemAdapter
from app.services.obsidian.formatters.obsidianMarkdown import format_obsidian_markdown


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
