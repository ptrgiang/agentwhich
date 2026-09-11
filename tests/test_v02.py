import json
from pathlib import Path

from agentwhich.adapters.claude import ClaudeResolver
from agentwhich.adapters.copilot import CopilotResolver
from agentwhich.adapters.gemini import GeminiResolver
from agentwhich.cli import main
from agentwhich.compare import compare_results
from agentwhich.discovery import layer
from agentwhich.model import ResolutionResult


def test_claude_inline_import_and_code_span_skip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'shared.md').write_text('shared', encoding='utf-8')
    (repo / 'CLAUDE.md').write_text('See @shared.md. Ignore `@missing.md`.', encoding='utf-8')

    result = ClaudeResolver().resolve(repo, repo)
    assert any(item.path == repo / 'shared.md' and item.phase == 'import' for item in result.layers)
    assert not any('missing.md' in warning for warning in result.warnings)


def test_claude_path_rule_and_descendant_target(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    repo = tmp_path / 'repo'
    target = repo / 'src' / 'api' / 'handler.ts'
    target.parent.mkdir(parents=True)
    rules = repo / '.claude' / 'rules'
    rules.mkdir(parents=True)
    rule = rules / 'api.md'
    rule.write_text('---\npaths:\n  - "src/api/**/*.ts"\n---\nAPI rules', encoding='utf-8')
    nested = repo / 'src' / 'CLAUDE.md'
    nested.write_text('src instructions', encoding='utf-8')

    result = ClaudeResolver().resolve(repo, repo, target)
    active_target = {item.path for item in result.layers if item.phase == 'target'}
    assert rule in active_target
    assert nested in active_target


def test_claude_path_rule_without_target_is_lazy(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    repo = tmp_path / 'repo'
    rules = repo / '.claude' / 'rules'
    rules.mkdir(parents=True)
    rule = rules / 'python.md'
    rule.write_text('---\npaths: ["**/*.py"]\n---\nPython', encoding='utf-8')

    result = ClaudeResolver().resolve(repo, repo)
    assert any(item.path == rule and item.phase == 'lazy' for item in result.layers)


def test_gemini_target_adds_jit_context(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    repo = tmp_path / 'repo'
    nested = repo / 'packages' / 'web'
    nested.mkdir(parents=True)
    (repo / 'GEMINI.md').write_text('root', encoding='utf-8')
    nested_context = nested / 'GEMINI.md'
    nested_context.write_text('web', encoding='utf-8')

    result = GeminiResolver().resolve(repo, repo, nested / 'app.ts')
    assert any(item.path == nested_context and item.phase == 'target' for item in result.layers)


def test_gemini_custom_context_filename(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    repo = tmp_path / 'repo'
    (repo / '.gemini').mkdir(parents=True)
    (repo / '.gemini' / 'settings.json').write_text(
        '{"context": {"fileName": ["AGENTS.md", "GEMINI.md"]}}', encoding='utf-8'
    )
    custom = repo / 'AGENTS.md'
    custom.write_text('agent context', encoding='utf-8')

    result = GeminiResolver().resolve(repo, repo)
    assert any(item.path == custom for item in result.layers)


def test_copilot_combines_standard_instruction_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    repo = tmp_path / 'repo'
    (repo / '.github').mkdir(parents=True)
    (repo / '.github' / 'copilot-instructions.md').write_text('repo', encoding='utf-8')
    (repo / 'AGENTS.md').write_text('agents', encoding='utf-8')
    (repo / 'CLAUDE.md').write_text('claude', encoding='utf-8')
    (repo / 'GEMINI.md').write_text('gemini', encoding='utf-8')

    result = CopilotResolver().resolve(repo, repo)
    names = {item.path.name for item in result.layers if item.phase == 'startup'}
    assert {'copilot-instructions.md', 'AGENTS.md', 'CLAUDE.md', 'GEMINI.md'} <= names


def test_copilot_apply_to_and_import_support(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    repo = tmp_path / 'repo'
    rules = repo / '.github' / 'instructions'
    rules.mkdir(parents=True)
    rule = rules / 'python.instructions.md'
    rule.write_text('---\napplyTo: "**/*.py"\n---\nPython rules', encoding='utf-8')
    (repo / 'shared.md').write_text('shared', encoding='utf-8')
    (repo / 'AGENTS.md').write_text('Use @shared.md', encoding='utf-8')
    (repo / 'GEMINI.md').write_text('Do not expand @missing.md', encoding='utf-8')

    result = CopilotResolver().resolve(repo, repo, repo / 'src' / 'main.py')
    assert any(item.path == rule and item.phase == 'target' for item in result.layers)
    assert any(item.path == repo / 'shared.md' and item.phase == 'import' for item in result.layers)
    assert not any('missing.md' in warning for warning in result.warnings)


def test_copilot_deduplicates_identical_content(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'AGENTS.md').write_text('same', encoding='utf-8')
    (repo / 'CLAUDE.md').write_text('same', encoding='utf-8')

    result = CopilotResolver().resolve(repo, repo)
    assert len([item for item in result.layers if item.phase == 'startup']) == 1
    assert any('deduplicated' in item.reason for item in result.skipped)


def test_compare_counts_target_as_active(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    path = repo / 'rule.md'
    path.write_text('same', encoding='utf-8')
    first = ResolutionResult(agent='a', repository=repo, cwd=repo)
    second = ResolutionResult(agent='b', repository=repo, cwd=repo)
    first.layers.append(layer(agent='a', path=path, phase='target', scope='rule', reason='match'))
    second.layers.append(layer(agent='b', path=path, phase='startup', scope='rule', reason='startup'))

    comparison = compare_results([first, second])
    assert not comparison.divergent
    assert comparison.shared_paths == [path]


def test_relative_target_is_resolved_from_cwd(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    repo = tmp_path / 'repo'
    rules = repo / '.github' / 'instructions'
    rules.mkdir(parents=True)
    (rules / 'python.instructions.md').write_text(
        '---\napplyTo: "src/**/*.py"\n---\nPython', encoding='utf-8'
    )

    code = main([
        'explain', '--agent', 'copilot', '--repo', str(repo), '--cwd', str(repo),
        '--target', 'src/main.py', '--format', 'json',
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['target'] == str(repo / 'src' / 'main.py')
    assert any(item['phase'] == 'target' for item in payload['layers'])
