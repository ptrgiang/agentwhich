import hashlib
import json
import subprocess
from pathlib import Path

from agentwhich.cli import main
from agentwhich.impact import analyze_changes
from agentwhich.snapshot import capture_snapshot


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ['git', '-C', str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
    )
    return completed.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / 'repo'
    repo.mkdir()
    _git(repo, 'init')
    _git(repo, 'config', 'user.email', 'agentwhich@example.test')
    _git(repo, 'config', 'user.name', 'agentwhich tests')
    return repo


def _commit(repo: Path, message: str) -> str:
    _git(repo, 'add', '.')
    _git(repo, 'commit', '-m', message)
    return _git(repo, 'rev-parse', 'HEAD')


def test_snapshot_ref_uses_historical_instruction_content(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / 'AGENTS.md').write_text('base instructions', encoding='utf-8')
    (repo / 'app.py').write_text('print("base")\n', encoding='utf-8')
    base = _commit(repo, 'base')
    (repo / 'AGENTS.md').write_text('working tree instructions', encoding='utf-8')

    report = capture_snapshot(repo, repo, ['codex'], [repo / 'app.py'], ref=base)
    layers = report.contexts[0].agents[0].layers
    assert [item.path for item in layers] == ['AGENTS.md']
    expected = hashlib.sha256(b'base instructions').hexdigest()
    assert layers[0].sha256 == expected
    assert report.commit == base


def test_changed_detects_instruction_content_impact_on_changed_code(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / 'AGENTS.md').write_text('one', encoding='utf-8')
    (repo / 'app.py').write_text('value = 1\n', encoding='utf-8')
    base = _commit(repo, 'base')

    (repo / 'AGENTS.md').write_text('two', encoding='utf-8')
    (repo / 'app.py').write_text('value = 2\n', encoding='utf-8')
    _commit(repo, 'head')

    report = analyze_changes(repo, repo, ['codex'], base=base)
    app = next(item for item in report.affected_targets if item.path == 'app.py')
    codex = app.agents[0]
    assert codex.modified == ('AGENTS.md',)
    assert report.affected_agents == ('codex',)
    assert report.has_confirmed_impact


def test_changed_code_only_has_no_context_impact(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / 'AGENTS.md').write_text('stable', encoding='utf-8')
    (repo / 'app.py').write_text('value = 1\n', encoding='utf-8')
    base = _commit(repo, 'base')
    (repo / 'app.py').write_text('value = 2\n', encoding='utf-8')
    _commit(repo, 'head')

    report = analyze_changes(repo, repo, ['codex'], base=base)
    assert [item.path for item in report.changed] == ['app.py']
    assert not report.affected_targets
    assert not report.instruction_sources
    assert not report.has_confirmed_impact


def test_changed_detects_new_claude_scoped_rule_for_changed_target(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    source = repo / 'src' / 'app.py'
    source.parent.mkdir()
    source.write_text('value = 1\n', encoding='utf-8')
    base = _commit(repo, 'base')

    rules = repo / '.claude' / 'rules'
    rules.mkdir(parents=True)
    rule = rules / 'python.md'
    rule.write_text('---\npaths: ["src/**/*.py"]\n---\nUse Python rules.\n', encoding='utf-8')
    source.write_text('value = 2\n', encoding='utf-8')
    _commit(repo, 'head')

    report = analyze_changes(repo, repo, ['claude'], base=base)
    app = next(item for item in report.affected_targets if item.path == 'src/app.py')
    assert app.agents[0].added == ('.claude/rules/python.md',)
    assert report.instruction_sources[0].agents == ('claude',)


def test_path_rename_can_remove_target_scoped_context(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    rules = repo / '.claude' / 'rules'
    rules.mkdir(parents=True)
    rule = rules / 'python.md'
    rule.write_text('---\npaths: ["src/**/*.py"]\n---\nUse Python rules.\n', encoding='utf-8')
    source = repo / 'src' / 'app.py'
    source.parent.mkdir()
    source.write_text('value = 1\n', encoding='utf-8')
    base = _commit(repo, 'base')

    destination = repo / 'docs' / 'app.py'
    destination.parent.mkdir()
    source.rename(destination)
    _commit(repo, 'rename target')

    report = analyze_changes(repo, repo, ['claude'], base=base)
    renamed = next(item for item in report.affected_targets if item.path == 'docs/app.py')
    assert renamed.agents[0].removed == ('.claude/rules/python.md',)


def test_changed_cwd_scopes_monorepo_paths(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    package_a = repo / 'packages' / 'a'
    package_b = repo / 'packages' / 'b'
    package_a.mkdir(parents=True)
    package_b.mkdir(parents=True)
    (repo / 'AGENTS.md').write_text('stable', encoding='utf-8')
    (package_a / 'app.py').write_text('a = 1\n', encoding='utf-8')
    (package_b / 'app.py').write_text('b = 1\n', encoding='utf-8')
    base = _commit(repo, 'base')

    (package_a / 'app.py').write_text('a = 2\n', encoding='utf-8')
    (package_b / 'app.py').write_text('b = 2\n', encoding='utf-8')
    _commit(repo, 'head')

    report = analyze_changes(repo, package_a, ['codex'], base=base)
    assert [item.path for item in report.changed] == ['packages/a/app.py']
    assert report.cwd == 'packages/a'


def test_cli_fail_on_impact_only_fails_confirmed_impact(tmp_path: Path, capsys) -> None:
    repo = _init_repo(tmp_path)
    (repo / 'AGENTS.md').write_text('one', encoding='utf-8')
    (repo / 'app.py').write_text('value = 1\n', encoding='utf-8')
    base = _commit(repo, 'base')
    (repo / 'AGENTS.md').write_text('two', encoding='utf-8')
    (repo / 'app.py').write_text('value = 2\n', encoding='utf-8')
    _commit(repo, 'head')

    code = main(
        [
            'changed',
            '--repo',
            str(repo),
            '--cwd',
            str(repo),
            '--agents',
            'codex',
            '--base',
            base,
            '--fail-on-impact',
            '--format',
            'json',
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload['status'] == 'changed'


def test_potential_scoped_rule_change_does_not_fail_on_impact(tmp_path: Path, capsys) -> None:
    repo = _init_repo(tmp_path)
    (repo / 'README.md').write_text('base\n', encoding='utf-8')
    base = _commit(repo, 'base')
    rules = repo / '.claude' / 'rules'
    rules.mkdir(parents=True)
    (rules / 'python.md').write_text('---\npaths: ["src/**/*.py"]\n---\nPython\n', encoding='utf-8')
    _commit(repo, 'rule only')

    code = main(
        [
            'changed',
            '--repo',
            str(repo),
            '--cwd',
            str(repo),
            '--agents',
            'claude',
            '--base',
            base,
            '--fail-on-impact',
            '--format',
            'json',
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload['status'] == 'potential-context-change'
    assert payload['instruction_sources'][0]['path'] == '.claude/rules/python.md'
