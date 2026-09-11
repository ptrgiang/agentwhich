from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .gitrefs import ChangedFile, changed_files, git_root, merge_base, resolve_ref, within_scope
from .snapshot import AgentContext, LayerState, capture_snapshot


@dataclass(frozen=True, slots=True)
class AgentImpact:
    agent: str
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()
    phase_changed: tuple[str, ...] = ()
    order_changed: bool = False

    @property
    def affected(self) -> bool:
        return bool(self.added or self.removed or self.modified or self.phase_changed or self.order_changed)

    def to_dict(self) -> dict[str, object]:
        return {
            'agent': self.agent,
            'affected': self.affected,
            'added': list(self.added),
            'removed': list(self.removed),
            'modified': list(self.modified),
            'phase_changed': list(self.phase_changed),
            'order_changed': self.order_changed,
        }


@dataclass(frozen=True, slots=True)
class TargetImpact:
    path: str
    status: str
    agents: tuple[AgentImpact, ...]

    @property
    def affected(self) -> bool:
        return any(item.affected for item in self.agents)

    def to_dict(self) -> dict[str, object]:
        return {
            'path': self.path,
            'status': self.status,
            'affected': self.affected,
            'agents': [item.to_dict() for item in self.agents],
        }


@dataclass(frozen=True, slots=True)
class InstructionSourceChange:
    path: str
    status: str
    agents: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {'path': self.path, 'status': self.status, 'agents': list(self.agents)}


@dataclass(frozen=True, slots=True)
class ImpactReport:
    repository: Path
    cwd: str
    base: str
    head: str
    base_commit: str
    head_commit: str
    changed: tuple[ChangedFile, ...]
    targets: tuple[TargetImpact, ...]
    instruction_sources: tuple[InstructionSourceChange, ...]

    @property
    def affected_targets(self) -> tuple[TargetImpact, ...]:
        return tuple(item for item in self.targets if item.affected)

    @property
    def affected_agents(self) -> tuple[str, ...]:
        names = {impact.agent for target in self.affected_targets for impact in target.agents if impact.affected}
        return tuple(sorted(names))

    @property
    def potential_agents(self) -> tuple[str, ...]:
        return tuple(sorted({agent for source in self.instruction_sources for agent in source.agents}))

    @property
    def has_confirmed_impact(self) -> bool:
        return bool(self.affected_targets)

    @property
    def has_potential_impact(self) -> bool:
        return bool(self.instruction_sources)

    def to_dict(self) -> dict[str, object]:
        return {
            'schema_version': 1,
            'status': (
                'changed'
                if self.has_confirmed_impact
                else 'potential-context-change'
                if self.has_potential_impact
                else 'no-context-change'
            ),
            'repository': str(self.repository),
            'cwd': self.cwd,
            'base': self.base,
            'head': self.head,
            'base_commit': self.base_commit,
            'head_commit': self.head_commit,
            'changed_files': [
                {
                    'status': item.status,
                    'old_path': item.old_path,
                    'new_path': item.new_path,
                    'path': item.path,
                }
                for item in self.changed
            ],
            'targets': [item.to_dict() for item in self.targets],
            'instruction_sources': [item.to_dict() for item in self.instruction_sources],
            'summary': {
                'changed_files': len(self.changed),
                'affected_targets': len(self.affected_targets),
                'affected_agents': list(self.affected_agents),
                'potential_agents': list(self.potential_agents),
            },
        }


def _relative_cwd(cwd: Path, repo: Path) -> str:
    try:
        relative = cwd.resolve(strict=False).relative_to(repo.resolve(strict=False)).as_posix()
    except ValueError as exc:
        raise ValueError(f'cwd {cwd} is outside repository {repo}') from exc
    return relative or '.'


def _target_path(item: ChangedFile, *, head: bool) -> str:
    if head:
        return item.new_path or item.old_path or ''
    return item.old_path or item.new_path or ''


def _by_agent(context) -> dict[str, AgentContext]:
    return {item.agent: item for item in context.agents}


def _layer_map(context: AgentContext) -> dict[str, LayerState]:
    return {item.path: item for item in context.layers}


def _compare_agent(before: AgentContext, after: AgentContext) -> AgentImpact:
    old = _layer_map(before)
    new = _layer_map(after)
    old_paths = set(old)
    new_paths = set(new)
    shared = old_paths & new_paths
    added = tuple(sorted(new_paths - old_paths))
    removed = tuple(sorted(old_paths - new_paths))
    modified = tuple(sorted(path for path in shared if old[path].sha256 != new[path].sha256))
    phase_changed = tuple(sorted(path for path in shared if old[path].phase != new[path].phase))
    old_order = [item.path for item in before.layers]
    new_order = [item.path for item in after.layers]
    order_changed = not added and not removed and old_order != new_order
    return AgentImpact(
        agent=after.agent,
        added=added,
        removed=removed,
        modified=modified,
        phase_changed=phase_changed,
        order_changed=order_changed,
    )


def _instruction_agents(path: str) -> tuple[str, ...]:
    pure = PurePosixPath(path)
    name = pure.name
    parts = pure.parts
    agents: set[str] = set()

    if name in {'AGENTS.md', 'AGENTS.override.md'}:
        agents.update({'codex', 'copilot'})
    if name in {'CLAUDE.md', 'CLAUDE.local.md'}:
        agents.update({'claude', 'copilot'})
    if name == 'GEMINI.md':
        agents.update({'gemini', 'copilot'})
    if '.claude' in parts and 'rules' in parts and name.endswith('.md'):
        agents.add('claude')
    if len(parts) >= 2 and parts[-2:] == ('.github', 'copilot-instructions.md'):
        agents.add('copilot')
    if '.github' in parts and 'instructions' in parts and name.endswith('.instructions.md'):
        agents.add('copilot')
    if len(parts) >= 2 and parts[-2:] == ('.gemini', 'settings.json'):
        agents.add('gemini')
    return tuple(sorted(agents))


def _source_changes(items: list[ChangedFile], selected_agents: list[str]) -> tuple[InstructionSourceChange, ...]:
    selected = set(selected_agents)
    results: list[InstructionSourceChange] = []
    for item in items:
        candidates = tuple(agent for agent in _instruction_agents(item.path) if agent in selected)
        if candidates:
            results.append(InstructionSourceChange(path=item.path, status=item.status, agents=candidates))
    return tuple(results)


def analyze_changes(
    repo: Path,
    cwd: Path,
    agents: list[str],
    *,
    base: str,
    head: str = 'HEAD',
    max_targets: int = 200,
) -> ImpactReport:
    repo = git_root(repo.resolve(strict=False))
    cwd = cwd.resolve(strict=False)
    cwd_relative = _relative_cwd(cwd, repo)
    if max_targets < 0:
        raise ValueError('--max-targets must be a non-negative integer')

    base_ref_commit = resolve_ref(repo, base)
    head_commit = resolve_ref(repo, head)
    base_commit = merge_base(repo, base_ref_commit, head_commit)
    all_changed = changed_files(repo, base_commit, head_commit)
    scoped = [
        item
        for item in all_changed
        if within_scope(item.old_path, cwd_relative) or within_scope(item.new_path, cwd_relative)
    ]
    if max_targets and len(scoped) > max_targets:
        raise ValueError(
            f'{len(scoped)} changed paths exceed --max-targets={max_targets}; '
            'narrow --cwd or pass --max-targets 0 to disable the limit'
        )

    base_targets = [repo / _target_path(item, head=False) for item in scoped]
    head_targets = [repo / _target_path(item, head=True) for item in scoped]
    base_snapshot = capture_snapshot(repo, cwd, agents, base_targets, ref=base_commit)
    head_snapshot = capture_snapshot(repo, cwd, agents, head_targets, ref=head_commit)

    targets: list[TargetImpact] = []
    for changed, before_context, after_context in zip(
        scoped,
        base_snapshot.contexts,
        head_snapshot.contexts,
        strict=True,
    ):
        before_agents = _by_agent(before_context)
        after_agents = _by_agent(after_context)
        impacts = tuple(_compare_agent(before_agents[agent], after_agents[agent]) for agent in agents)
        targets.append(TargetImpact(path=changed.path, status=changed.status, agents=impacts))

    return ImpactReport(
        repository=repo,
        cwd=cwd_relative,
        base=base,
        head=head,
        base_commit=base_commit,
        head_commit=head_commit,
        changed=tuple(scoped),
        targets=tuple(targets),
        instruction_sources=_source_changes(scoped, agents),
    )


def render_impact(report: ImpactReport, fmt: str = 'text') -> str:
    if fmt == 'json':
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)

    lines = [
        (
            'PR IMPACT: CHANGED'
            if report.has_confirmed_impact
            else 'PR IMPACT: POTENTIAL'
            if report.has_potential_impact
            else 'PR IMPACT: NO CONTEXT CHANGE'
        ),
        f'Base: {report.base} ({report.base_commit[:12]})',
        f'Head: {report.head} ({report.head_commit[:12]})',
        f'Scope: {report.cwd}',
        f'Changed files: {len(report.changed)}',
    ]

    affected = report.affected_targets
    if affected:
        lines.extend(['', 'TARGET CONTEXT'])
        for target in affected:
            lines.append(f'  {target.status:<4} {target.path}')
            for impact in target.agents:
                if not impact.affected:
                    continue
                lines.append(f'    {impact.agent.upper()}')
                lines.extend(f'      + {path}' for path in impact.added)
                lines.extend(f'      - {path}' for path in impact.removed)
                lines.extend(f'      ~ {path} (content changed)' for path in impact.modified)
                lines.extend(f'      ~ {path} (phase changed)' for path in impact.phase_changed)
                if impact.order_changed:
                    lines.append('      ~ active instruction order changed')

    if report.instruction_sources:
        lines.extend(['', 'INSTRUCTION SOURCE CHANGES'])
        for source in report.instruction_sources:
            agents = ','.join(source.agents)
            lines.append(f'  {source.status:<4} {source.path} -> {agents} (potential broader impact)')

    lines.extend(
        [
            '',
            (
                f'Summary: {len(report.affected_targets)} affected target(s), '
                f'{len(report.affected_agents)} affected agent(s), '
                f'{len(report.potential_agents)} potential agent(s)'
            ),
        ]
    )
    return '\n'.join(lines)
