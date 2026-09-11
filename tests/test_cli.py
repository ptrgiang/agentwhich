from pathlib import Path

from agentwhich.cli import main


def test_cli_compare_json(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'codex-home'))
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'AGENTS.md').write_text('rule', encoding='utf-8')
    (repo / 'CLAUDE.md').write_text('rule', encoding='utf-8')

    code = main(['compare', '--repo', str(repo), '--cwd', str(repo), '--agents', 'codex,claude', '--format', 'json'])
    out = capsys.readouterr().out
    assert code == 0
    assert '"schema_version": 1' in out
    assert '"status": "divergent"' in out
