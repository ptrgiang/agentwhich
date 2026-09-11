from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .core import resolve
from .gitrefs import git_root, materialize_ref, resolve_ref
from .model import ResolutionResult, is_active


@dataclass(frozen=True, slots=True)
class LayerState:
    path: str
    phase: str
    sha256: str
    order: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            'path': self.path,
            'phase': self.phase,
            'sha256': self.sha256,
            'order': self.order,
        }


@dataclass(frozen=True, slots=True)
class AgentContext:
    agent: str
    target: str | None
    layers: tuple[LayerState, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            'agent': self.agent,
            'target': self.target,
            'layers': [item.to_dict() for item in self.layers],
        }


@dataclass(frozen=True, slots=True)
class TargetContext:
    target: str | None
    agents: tuple[AgentContext, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            'target': self.target,
            'agents': [item.to_dict() for item in self.agents],
        }


@dataclass(frozen=True, slots=True)
class SnapshotReport:
    repository: Path
    cwd: str
    ref: str | None
    commit: str | None
    contexts: tuple[TargetContext, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            'schema_version': 1,
            'repository': str(self.repository),
            'cwd': self.cwd,
            'ref': self.ref,
            'commit': self.commit,
            'contexts': [item.to_dict() for item in self.contexts],
        }


def _relative(path: Path, root: Path) -> str | None:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return None


def _cwd_relative(cwd: Path, repo: Path) -> str:
    relative = _relative(cwd, repo)
    if relative is None:
        raise ValueError(f'cwd {cwd} is outside repository {repo}')
    return relative or '.'


def _target_relative(target: Path | str | None, cwd: Path, repo: Path) -> str | None:
    if target is None:
        return None
    value = Path(target).expanduser()
    if not value.is_absolute():
        value = cwd / value
    relative = _relative(value, repo)
    if relative is None:
        raise ValueError(f'target {value} is outside repository {repo}')
    return relative


def context_from_result(result: ResolutionResult, target: str | None) -> AgentContext:
    layers: list[LayerState] = []
    for item in result.layers:
        if not is_active(item):
            continue
        relative = _relative(item.path, result.repository)
        if relative is None:
            continue
        layers.append(
            LayerState(
                path=relative,
                phase=item.phase,
                sha256=item.sha256,
                order=item.order,
            )
        )
    return AgentContext(agent=result.agent, target=target, layers=tuple(layers))


@contextmanager
def isolated_user_config() -> Iterator[None]:
    keys = ('HOME', 'USERPROFILE', 'CODEX_HOME', 'COPILOT_CUSTOM_INSTRUCTIONS_DIRS', 'XDG_CONFIG_HOME')
    previous = {key: os.environ.get(key) for key in keys}
    with tempfile.TemporaryDirectory(prefix='agentwhich-home-') as temp_home:
        home = Path(temp_home)
        os.environ['HOME'] = str(home)
        os.environ['USERPROFILE'] = str(home)
        os.environ['CODEX_HOME'] = str(home / '.codex')
        os.environ['XDG_CONFIG_HOME'] = str(home / '.config')
        os.environ.pop('COPILOT_CUSTOM_INSTRUCTIONS_DIRS', None)
        try:
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _capture_at_root(
    source_repo: Path,
    materialized_repo: Path,
    cwd_relative: str,
    agents: list[str],
    target_relatives: list[str | None],
    ref: str | None,
    commit: str | None,
) -> SnapshotReport:
    effective_cwd = materialized_repo if cwd_relative == '.' else materialized_repo / cwd_relative
    contexts: list[TargetContext] = []
    with isolated_user_config():
        for target_relative in target_relatives:
            target = materialized_repo / target_relative if target_relative is not None else None
            agent_contexts: list[AgentContext] = []
            for agent in agents:
                result = resolve(agent, cwd=effective_cwd, repo=materialized_repo, target=target)
                agent_contexts.append(context_from_result(result, target_relative))
            contexts.append(TargetContext(target=target_relative, agents=tuple(agent_contexts)))
    return SnapshotReport(
        repository=source_repo,
        cwd=cwd_relative,
        ref=ref,
        commit=commit,
        contexts=tuple(contexts),
    )


def capture_snapshot(
    repo: Path,
    cwd: Path,
    agents: list[str],
    targets: list[Path | str | None],
    *,
    ref: str | None = None,
) -> SnapshotReport:
    repo = repo.resolve(strict=False)
    cwd = cwd.resolve(strict=False)
    cwd_relative = _cwd_relative(cwd, repo)
    target_relatives = [_target_relative(target, cwd, repo) for target in targets] or [None]

    if ref is None:
        return _capture_at_root(repo, repo, cwd_relative, agents, target_relatives, None, None)

    repo = git_root(repo)
    cwd_relative = _cwd_relative(cwd, repo)
    target_relatives = [_target_relative(target, cwd, repo) for target in targets] or [None]
    commit = resolve_ref(repo, ref)
    with tempfile.TemporaryDirectory(prefix='agentwhich-ref-') as temp_dir:
        materialized = Path(temp_dir) / 'repo'
        materialize_ref(repo, commit, materialized)
        return _capture_at_root(repo, materialized, cwd_relative, agents, target_relatives, ref, commit)


def render_snapshot(report: SnapshotReport, fmt: str = 'text') -> str:
    if fmt == 'json':
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)

    lines = ['SNAPSHOT', f'Repository: {report.repository}', f'CWD: {report.cwd}']
    if report.ref is not None:
        lines.append(f'Ref: {report.ref} ({(report.commit or "")[:12]})')
    else:
        lines.append('Ref: working tree')

    for context in report.contexts:
        lines.extend(['', f'Target: {context.target or "(startup context)"}'])
        for agent in context.agents:
            lines.append(f'  {agent.upper()}')
            if not agent.layers:
                lines.append('    (no active repository instruction files)')
                continue
            for item in agent.layers:
                order = item.order if item.order is not None else '-'
                lines.append(f'    {order} [{item.phase}] {item.path} {item.sha256[:12]}')
    return '\n'.join(lines)
