import json
from pathlib import Path

import pytest

from agentwhich.checks import (
    RULE_FORBIDDEN_ACTIVE,
    RULE_MAX_ACTIVE,
    RULE_REQUIRED_MISSING,
    evaluate_check,
)
from agentwhich.cli import main
from agentwhich.compare import compare_results
from agentwhich.model import InstructionLayer, ResolutionResult
from agentwhich.policy import AgentPolicy, Policy, load_policy
from agentwhich.sarif import to_sarif


def _layer(agent: str, path: Path, order: int = 1) -> InstructionLayer:
    return InstructionLayer(
        agent=agent,
        path=path,
        phase='startup',
        scope='repository',
        reason='test',
        order=order,
    )


def test_load_policy_parses_rules(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    policy_path = repo / '.agentwhich.toml'
    policy_path.write_text(
        '''version = 1
agents = ["codex", "claude"]
require_instructions = true
fail_on_warnings = true

[rules.codex]
require = ["AGENTS.md"]
forbid = ["**/AGENTS.override.md"]
max_active = 2
''',
        encoding='utf-8',
    )

    policy = load_policy(None, repo)
    assert policy.path == policy_path
    assert policy.agents == ('codex', 'claude')
    assert policy.require_instructions is True
    assert policy.fail_on_warnings is True
    assert policy.rules['codex'].require == ('AGENTS.md',)
    assert policy.rules['codex'].max_active == 2


def test_load_policy_rejects_unknown_version(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / '.agentwhich.toml').write_text('version = 2\n', encoding='utf-8')
    with pytest.raises(ValueError, match='unsupported policy version'):
        load_policy(None, repo)


def test_policy_require_forbid_and_max_active(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    nested = repo / 'services' / 'api'
    nested.mkdir(parents=True)
    agents = repo / 'AGENTS.md'
    override = nested / 'AGENTS.override.md'
    agents.write_text('root', encoding='utf-8')
    override.write_text('nested', encoding='utf-8')
    result = ResolutionResult(
        agent='codex',
        repository=repo,
        cwd=repo,
        layers=[_layer('codex', agents, 1), _layer('codex', override, 2)],
    )
    policy = Policy(
        path=repo / '.agentwhich.toml',
        rules={
            'codex': AgentPolicy(
                require=('missing.md',),
                forbid=('**/AGENTS.override.md',),
                max_active=1,
            )
        },
    )
    report = evaluate_check(compare_results([result]), policy)
    assert {item.rule_id for item in report.violations} == {
        RULE_REQUIRED_MISSING,
        RULE_FORBIDDEN_ACTIVE,
        RULE_MAX_ACTIVE,
    }


def test_policy_glob_is_path_segment_aware(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    nested = repo / 'services' / 'api'
    nested.mkdir(parents=True)
    nested_file = nested / 'CLAUDE.local.md'
    nested_file.write_text('local', encoding='utf-8')
    result = ResolutionResult(
        agent='claude',
        repository=repo,
        cwd=repo,
        layers=[_layer('claude', nested_file)],
    )
    policy = Policy(rules={'claude': AgentPolicy(forbid=('*.md',))})
    report = evaluate_check(compare_results([result]), policy)
    assert report.passed

    recursive = Policy(rules={'claude': AgentPolicy(forbid=('**/*.md',))})
    report = evaluate_check(compare_results([result]), recursive)
    assert not report.passed


def test_sarif_uses_policy_location_for_missing_rule(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    policy_path = repo / '.agentwhich.toml'
    policy_path.write_text('version = 1\n', encoding='utf-8')
    result = ResolutionResult(agent='codex', repository=repo, cwd=repo)
    policy = Policy(path=policy_path, rules={'codex': AgentPolicy(require=('AGENTS.md',))})
    report = evaluate_check(compare_results([result]), policy)

    sarif = to_sarif(report, '0.3.0')
    assert sarif['version'] == '2.1.0'
    first = sarif['runs'][0]['results'][0]
    assert first['ruleId'] == RULE_REQUIRED_MISSING
    assert first['locations'][0]['physicalLocation']['artifactLocation']['uri'] == '.agentwhich.toml'


def test_cli_check_exit_codes_and_json_output(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'codex-home'))
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'AGENTS.md').write_text('rule', encoding='utf-8')
    (repo / '.agentwhich.toml').write_text(
        '''version = 1
agents = ["codex"]

[rules.codex]
require = ["AGENTS.md"]
''',
        encoding='utf-8',
    )

    code = main(['check', '--repo', str(repo), '--cwd', str(repo), '--format', 'json'])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out['status'] == 'pass'

    (repo / '.agentwhich.toml').write_text(
        '''version = 1
agents = ["codex"]

[rules.codex]
require = ["missing.md"]
''',
        encoding='utf-8',
    )
    code = main(['check', '--repo', str(repo), '--cwd', str(repo), '--format', 'json'])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out['status'] == 'fail'
    assert out['violations'][0]['rule_id'] == RULE_REQUIRED_MISSING


def test_cli_check_writes_sarif(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'codex-home'))
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'AGENTS.md').write_text('rule', encoding='utf-8')
    (repo / '.agentwhich.toml').write_text(
        '''version = 1
agents = ["codex"]

[rules.codex]
forbid = ["AGENTS.md"]
''',
        encoding='utf-8',
    )
    output = tmp_path / 'agentwhich.sarif'
    code = main(
        [
            'check',
            '--repo',
            str(repo),
            '--cwd',
            str(repo),
            '--format',
            'sarif',
            '--output',
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding='utf-8'))
    assert code == 1
    assert payload['version'] == '2.1.0'
    assert payload['runs'][0]['results'][0]['ruleId'] == RULE_FORBIDDEN_ACTIVE


def test_action_metadata_is_composite_and_uploads_sarif() -> None:
    action = (Path(__file__).parents[1] / 'action.yml').read_text(encoding='utf-8')
    assert 'using: composite' in action
    assert 'github/codeql-action/upload-sarif@v4' in action
    assert 'python -m pip install "$GITHUB_ACTION_PATH"' in action


def test_policy_rejects_unknown_fields(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / '.agentwhich.toml').write_text('version = 1\nrequre_instructions = true\n', encoding='utf-8')
    with pytest.raises(ValueError, match='unknown policy field'):
        load_policy(None, repo)


def test_divergence_gate_ignores_global_instruction_paths(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    home = tmp_path / 'home'
    home.mkdir()
    codex_global = home / 'AGENTS.md'
    claude_global = home / 'CLAUDE.md'
    codex_global.write_text('a', encoding='utf-8')
    claude_global.write_text('b', encoding='utf-8')
    codex = ResolutionResult(
        agent='codex',
        repository=repo,
        cwd=repo,
        layers=[_layer('codex', codex_global)],
    )
    claude = ResolutionResult(
        agent='claude',
        repository=repo,
        cwd=repo,
        layers=[_layer('claude', claude_global)],
    )
    comparison = compare_results([codex, claude])
    assert comparison.divergent
    report = evaluate_check(comparison, Policy(fail_on_divergence=True))
    assert report.passed
