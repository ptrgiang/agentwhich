from pathlib import Path

from agentwhich.compare import compare_results
from agentwhich.core import resolve


def test_compare_marks_divergence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'codex-home'))
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'AGENTS.md').write_text('codex', encoding='utf-8')
    (repo / 'CLAUDE.md').write_text('claude', encoding='utf-8')

    report = compare_results([
        resolve('codex', cwd=repo, repo=repo),
        resolve('claude', cwd=repo, repo=repo),
    ])

    assert report.divergent is True
    assert (repo / 'AGENTS.md').resolve() in report.by_agent_only['codex']
    assert (repo / 'CLAUDE.md').resolve() in report.by_agent_only['claude']
