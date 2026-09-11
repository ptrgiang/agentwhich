from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .adapters import RESOLVERS
from .compare import compare_results
from .core import resolve
from .render import render_comparison, render_result

VERSION = '0.2.0'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='agentwhich',
        description='which + diff for AI coding instructions',
    )
    parser.add_argument('--version', action='version', version=f'agentwhich {VERSION}')
    sub = parser.add_subparsers(dest='command', required=True)

    explain = sub.add_parser('explain', help='explain instruction sources for one agent')
    explain.add_argument('--agent', required=True, choices=sorted(RESOLVERS))
    explain.add_argument('--cwd', default='.', help='working directory to resolve from')
    explain.add_argument('--repo', default=None, help='repository root; auto-detected from .git by default')
    explain.add_argument('--target', default=None, help='optional target file for path/JIT-scoped instructions')
    explain.add_argument('--format', choices=('text', 'json'), default='text')

    compare = sub.add_parser('compare', help='compare instruction sources across agents')
    compare.add_argument(
        '--agents',
        default='codex,claude,gemini,copilot',
        help='comma-separated agent names',
    )
    compare.add_argument('--cwd', default='.', help='working directory to resolve from')
    compare.add_argument('--repo', default=None, help='repository root; auto-detected from .git by default')
    compare.add_argument('--target', default=None, help='optional target file for path/JIT-scoped instructions')
    compare.add_argument('--format', choices=('text', 'json'), default='text')
    return parser


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == 'explain':
            result = resolve(
                args.agent,
                cwd=Path(args.cwd),
                repo=_optional_path(args.repo),
                target=_optional_path(args.target),
            )
            print(render_result(result, args.format))
            return 0

        agents = [item.strip().lower() for item in args.agents.split(',') if item.strip()]
        unknown = [agent for agent in agents if agent not in RESOLVERS]
        if unknown:
            raise ValueError(f'unsupported agent(s): {", ".join(unknown)}')
        if len(agents) < 2:
            raise ValueError('compare requires at least two agents')
        results = [
            resolve(
                agent,
                cwd=Path(args.cwd),
                repo=_optional_path(args.repo),
                target=_optional_path(args.target),
            )
            for agent in agents
        ]
        print(render_comparison(compare_results(results), args.format))
        return 0
    except (OSError, ValueError) as exc:
        print(f'agentwhich: error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
