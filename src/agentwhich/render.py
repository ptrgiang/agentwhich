from __future__ import annotations

import json
from pathlib import Path

from .compare import Comparison
from .model import ResolutionResult, display_path


def _size(value: int) -> str:
    if value < 1024:
        return f'{value} B'
    return f'{value / 1024:.1f} KiB'


def render_result(result: ResolutionResult, fmt: str = 'text') -> str:
    if fmt == 'json':
        return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

    lines = [
        f'Agent: {result.agent}',
        f'Repository: {result.repository}',
        f'Working directory: {result.cwd}',
        '',
    ]
    active = [item for item in result.layers if item.phase in {'startup', 'import'}]
    lazy = [item for item in result.layers if item.phase not in {'startup', 'import'}]

    lines.append('ACTIVE / STARTUP')
    if not active:
        lines.append('  (none)')
    for item in active:
        prefix = f'{item.order}.' if item.order is not None else '-'
        lines.append(f'  {prefix} {display_path(item.path, result.repository)}')
        lines.append(f'     {item.reason} · {_size(item.byte_count)} · {item.line_count} lines')

    if result.skipped:
        lines.extend(['', 'SKIPPED'])
        for item in result.skipped:
            lines.append(f'  - {display_path(item.path, result.repository)}')
            lines.append(f'    {item.reason}')

    if lazy:
        lines.extend(['', 'LAZY / TARGET-DEPENDENT'])
        for item in lazy:
            lines.append(f'  ? {display_path(item.path, result.repository)}')
            lines.append(f'    {item.reason}')

    if result.warnings:
        lines.extend(['', 'NOTES'])
        lines.extend(f'  ! {warning}' for warning in result.warnings)

    lines.extend(['', f'Summary: {len(active)} active source(s), {sum(item.byte_count for item in active)} bytes'])
    return '\n'.join(lines)


def render_comparison(comparison: Comparison, fmt: str = 'text') -> str:
    if fmt == 'json':
        payload = {
            'schema_version': 1,
            'status': 'divergent' if comparison.divergent else 'equivalent-source-set',
            'results': [result.to_dict() for result in comparison.results],
            'shared_paths': [str(path) for path in comparison.shared_paths],
            'only': {agent: [str(path) for path in paths] for agent, paths in comparison.by_agent_only.items()},
            'duplicate_hashes': {
                digest: [{'agent': agent, 'path': str(path)} for agent, path in items]
                for digest, items in comparison.duplicate_hashes.items()
            },
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    repo = comparison.results[0].repository if comparison.results else Path.cwd()
    lines: list[str] = []
    for result in comparison.results:
        lines.extend([result.agent.upper(), '-' * len(result.agent)])
        active = [item for item in result.layers if item.phase in {'startup', 'import'}]
        if not active:
            lines.append('  (no startup sources found)')
        for item in active:
            lines.append(f'  {item.order or "-":>2} {display_path(item.path, repo)}')
        lazy_count = sum(item.phase not in {'startup', 'import'} for item in result.layers)
        if lazy_count:
            lines.append(f'   ? {lazy_count} lazy/target-dependent candidate(s)')
        lines.append('')

    lines.append('DIFF')
    lines.append('----')
    for agent, paths in comparison.by_agent_only.items():
        lines.append(f'  {agent}-only:')
        if paths:
            lines.extend(f'    {display_path(path, repo)}' for path in paths)
        else:
            lines.append('    (none)')
    lines.append(f'  shared by all: {len(comparison.shared_paths)}')
    lines.append(f'  exact duplicate contents across agents: {len(comparison.duplicate_hashes)}')
    lines.append(f'  status: {"divergent" if comparison.divergent else "equivalent source set"}')
    return '\n'.join(lines)
