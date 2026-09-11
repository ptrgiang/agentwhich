from pathlib import Path

from agentwhich.adapters.claude import ClaudeResolver
from agentwhich.adapters.gemini import GeminiResolver


def test_claude_hierarchy_and_import(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    repo = tmp_path / 'repo'
    cwd = repo / 'services' / 'api'
    cwd.mkdir(parents=True)
    (repo / 'shared.md').write_text('shared', encoding='utf-8')
    (repo / 'CLAUDE.md').write_text('@shared.md\nroot', encoding='utf-8')
    (cwd / 'CLAUDE.local.md').write_text('local', encoding='utf-8')

    result = ClaudeResolver().resolve(repo, cwd)
    names = [item.path.name for item in result.layers if item.phase in {'startup', 'import'}]
    assert names == ['CLAUDE.md', 'CLAUDE.local.md', 'shared.md']


def test_gemini_hierarchy(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    cwd = repo / 'app'
    cwd.mkdir(parents=True)
    (repo / 'GEMINI.md').write_text('root', encoding='utf-8')
    (cwd / 'GEMINI.md').write_text('nested', encoding='utf-8')

    result = GeminiResolver().resolve(repo, cwd)
    assert [item.path for item in result.layers if item.phase == 'startup'] == [repo / 'GEMINI.md', cwd / 'GEMINI.md']
