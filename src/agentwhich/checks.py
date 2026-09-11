from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .compare import Comparison
from .model import InstructionLayer, display_path, is_active
from .policy import Policy

RULE_MISSING_INSTRUCTIONS = 'AW001'
RULE_REQUIRED_MISSING = 'AW002'
RULE_FORBIDDEN_ACTIVE = 'AW003'
RULE_MAX_ACTIVE = 'AW004'
RULE_WARNING = 'AW005'
RULE_DIVERGENCE = 'AW006'
RULE_TARGET_REQUIRED = 'AW007'


@dataclass(frozen=True, slots=True)
class Violation:
    rule_id: str
    message: str
    agent: str | None = None
    path: Path | None = None

    def to_dict(self, repo: Path) -> dict[str, object]:
        return {
            'rule_id': self.rule_id,
            'message': self.message,
            'agent': self.agent,
            'path': display_path(self.path, repo) if self.path is not None else None,
        }


@dataclass(slots=True)
class CheckReport:
    comparison: Comparison
    policy: Policy
    violations: list[Violation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations

    @property
    def repository(self) -> Path:
        if self.comparison.results:
            return self.comparison.results[0].repository
        return Path.cwd().resolve(strict=False)

    @property
    def repository_divergent(self) -> bool:
        repo_sets = [
            {item.path.resolve(strict=False) for item in _repo_active_layers(result)}
            for result in self.comparison.results
        ]
        return any(paths != repo_sets[0] for paths in repo_sets[1:]) if repo_sets else False

    def to_dict(self) -> dict[str, object]:
        return {
            'schema_version': 1,
            'status': 'pass' if self.passed else 'fail',
            'repository': str(self.repository),
            'policy': str(self.policy.path) if self.policy.path is not None else None,
            'violations': [item.to_dict(self.repository) for item in self.violations],
            'comparison': {
                'divergent': self.comparison.divergent,
                'repository_divergent': self.repository_divergent,
                'agents': [result.agent for result in self.comparison.results],
            },
        }


def _repo_relative(path: Path, repo: Path) -> str | None:
    try:
        return path.resolve(strict=False).relative_to(repo.resolve(strict=False)).as_posix()
    except ValueError:
        return None


def _brace_expand(pattern: str) -> list[str]:
    match = re.search(r'\{([^{}]+)\}', pattern)
    if match is None:
        return [pattern]
    results: list[str] = []
    for choice in match.group(1).split(','):
        if choice:
            expanded = pattern[: match.start()] + choice + pattern[match.end() :]
            results.extend(_brace_expand(expanded))
    return results or [pattern]


def _glob_regex(pattern: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == '*':
            if index + 1 < len(pattern) and pattern[index + 1] == '*':
                index += 2
                if index < len(pattern) and pattern[index] == '/':
                    out.append('(?:.*/)?')
                    index += 1
                else:
                    out.append('.*')
                continue
            out.append('[^/]*')
        elif char == '?':
            out.append('[^/]')
        else:
            out.append(re.escape(char))
        index += 1
    return ''.join(out)


def _match(pattern: str, rel_path: str) -> bool:
    for expanded in _brace_expand(pattern.removeprefix('./')):
        if re.fullmatch(_glob_regex(expanded), rel_path):
            return True
    return False


def _repo_active_layers(result) -> list[InstructionLayer]:
    repo = result.repository.resolve(strict=False)
    active: list[InstructionLayer] = []
    for item in result.layers:
        if is_active(item) and _repo_relative(item.path, repo) is not None:
            active.append(item)
    return active


def evaluate_check(
    comparison: Comparison,
    policy: Policy,
    *,
    require_instructions: bool = False,
    fail_on_warnings: bool = False,
    fail_on_divergence: bool = False,
    require_target: bool = False,
) -> CheckReport:
    report = CheckReport(comparison=comparison, policy=policy)
    must_have_instructions = policy.require_instructions or require_instructions
    warnings_are_errors = policy.fail_on_warnings or fail_on_warnings
    divergence_is_error = policy.fail_on_divergence or fail_on_divergence
    target_is_required = policy.require_target or require_target

    if target_is_required and any(result.target is None for result in comparison.results):
        report.violations.append(
            Violation(
                rule_id=RULE_TARGET_REQUIRED,
                message='policy requires a target path, but --target was not provided',
                path=policy.path,
            )
        )

    for result in comparison.results:
        active = _repo_active_layers(result)
        rel_paths = [(_repo_relative(item.path, result.repository) or '', item) for item in active]

        if must_have_instructions and not active:
            report.violations.append(
                Violation(
                    rule_id=RULE_MISSING_INSTRUCTIONS,
                    agent=result.agent,
                    message=f'{result.agent} has no active repository instruction files',
                    path=policy.path,
                )
            )

        agent_policy = policy.rules.get(result.agent)
        if agent_policy is not None:
            for pattern in agent_policy.require:
                if not any(_match(pattern, rel_path) for rel_path, _ in rel_paths):
                    report.violations.append(
                        Violation(
                            rule_id=RULE_REQUIRED_MISSING,
                            agent=result.agent,
                            message=f'{result.agent} is missing required active instruction matching {pattern!r}',
                            path=policy.path,
                        )
                    )
            for pattern in agent_policy.forbid:
                for rel_path, item in rel_paths:
                    if _match(pattern, rel_path):
                        report.violations.append(
                            Violation(
                                rule_id=RULE_FORBIDDEN_ACTIVE,
                                agent=result.agent,
                                message=f'{result.agent} activates forbidden instruction {rel_path!r}',
                                path=item.path,
                            )
                        )
            if agent_policy.max_active is not None and len(active) > agent_policy.max_active:
                report.violations.append(
                    Violation(
                        rule_id=RULE_MAX_ACTIVE,
                        agent=result.agent,
                        message=(
                            f'{result.agent} has {len(active)} active repository instructions; '
                            f'maximum is {agent_policy.max_active}'
                        ),
                        path=active[agent_policy.max_active].path if active else policy.path,
                    )
                )

        if warnings_are_errors:
            for warning in result.warnings:
                report.violations.append(
                    Violation(
                        rule_id=RULE_WARNING,
                        agent=result.agent,
                        message=f'{result.agent} resolver warning: {warning}',
                        path=policy.path,
                    )
                )

    if divergence_is_error and report.repository_divergent:
        report.violations.append(
            Violation(
                rule_id=RULE_DIVERGENCE,
                message='repository-local active instruction source sets diverge across selected agents',
                path=policy.path,
            )
        )

    return report


def render_check_report(report: CheckReport, fmt: str = 'text') -> str:
    if fmt == 'json':
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)

    lines = [f'CHECK: {"PASS" if report.passed else "FAIL"}']
    if report.policy.path is not None:
        lines.append(f'Policy: {display_path(report.policy.path, report.repository)}')
    lines.append(f'Agents: {", ".join(result.agent for result in report.comparison.results)}')
    if report.passed:
        lines.append('No policy violations found.')
        return '\n'.join(lines)

    lines.append('Violations:')
    for item in report.violations:
        agent = f' [{item.agent}]' if item.agent else ''
        location = f' ({display_path(item.path, report.repository)})' if item.path is not None else ''
        lines.append(f'  - {item.rule_id}{agent}: {item.message}{location}')
    return '\n'.join(lines)
