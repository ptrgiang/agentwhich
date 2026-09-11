from pathlib import Path

from agentwhich.adapters.codex import CodexResolver


def test_codex_override_shadows_same_directory_agents(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / 'home'
    repo = tmp_path / 'repo'
    cwd = repo / 'services' / 'api'
    cwd.mkdir(parents=True)
    (repo / 'AGENTS.md').write_text('root', encoding='utf-8')
    (cwd / 'AGENTS.md').write_text('normal', encoding='utf-8')
    (cwd / 'AGENTS.override.md').write_text('override', encoding='utf-8')
    monkeypatch.setenv('CODEX_HOME', str(home / '.codex'))

    result = CodexResolver().resolve(repo, cwd)

    assert [item.path.name for item in result.layers] == ['AGENTS.md', 'AGENTS.override.md']
    assert any(item.path.name == 'AGENTS.md' and item.path.parent == cwd for item in result.skipped)


def test_codex_fallback_names(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / 'codex-home'
    codex_home.mkdir()
    (codex_home / 'config.toml').write_text('project_doc_fallback_filenames = ["AI.md"]\n', encoding='utf-8')
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'AI.md').write_text('fallback', encoding='utf-8')
    monkeypatch.setenv('CODEX_HOME', str(codex_home))

    result = CodexResolver().resolve(repo, repo)
    assert [item.path.name for item in result.layers] == ['AI.md']
