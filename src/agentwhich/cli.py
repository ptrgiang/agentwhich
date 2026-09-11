from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .adapters import RESOLVERS
from .checks import evaluate_check, render_check_report
from .compare import compare_results
from .core import resolve
from .discovery import repository_root
from .policy import Policy, load_policy
from .render import render_comparison, render_result
from .sarif import render_sarif

VERSION = '0.3.0'
DEFAULT_AGENTS = 'codex,claude,gemini,copilot'


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
    compare.add_argument('--agents', default=DEFAULT_AGENTS, help='comma-separated agent names')
    compare.add_argument('--cwd', default='.', help='working directory to resolve from')
    compare.add_argument('--repo', default=None, help='repository root; auto-detected from .git by default')
    compare.add_argument('--target', default=None, help='optional target file for path/JIT-scoped instructions')
    compare.add_argument('--format', choices=('text', 'json'), default='text')

    check = sub.add_parser('check', help='enforce instruction policy and fail on violations')
    check.add_argument(
        '--agents',
        default=None,
        help='comma-separated agents; policy or all supported agents by default',
    )
    check.add_argument('--cwd', default='.', help='working directory to resolve from')
    check.add_argument('--repo', default=None, help='repository root; auto-detected from .git by default')
    check.add_argument('--target', default=None, help='optional target file for path/JIT-scoped instructions')
    check.add_argument('--policy', default=None, help='policy TOML; defaults to .agentwhich.toml when present')
    check.add_argument(
        '--require-instructions',
        action='store_true',
        help='require repo-local instructions for every agent',
    )
    check.add_argument('--fail-on-warnings', action='store_true', help='treat resolver warnings as policy violations')
    check.add_argument(
        '--fail-on-divergence',
        action='store_true',
        help='fail when active source sets differ',
    )
    check.add_argument('--require-target', action='store_true', help='require --target to be provided')
    check.add_argument('--format', choices=('text', 'json', 'sarif'), default='text')
    check.add_argument('--output', default=None, help='write output to this file instead of stdout')
    return parser


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None


def _parse_agents(raw: str) -> list[str]:
    agents = list(dict.fromkeys(item.strip().lower() for item in raw.split(',') if item.strip()))
    unknown = [agent for agent in agents if agent not in RESOLVERS]
    if unknown:
        raise ValueError(f'unsupported agent(s): {", ".join(unknown)}')
    if not agents:
        raise ValueError('at least one agent is required')
    return agents


def _repo_path(cwd: Path, repo: Path | None) -> Path:
    cwd = cwd.expanduser().resolve(strict=False)
    if repo is not None:
        return repo.expanduser().resolve(strict=False)
    return repository_root(cwd)


def _policy_has_assertions(policy: Policy) -> bool:
    if policy.require_instructions or policy.fail_on_warnings or policy.fail_on_divergence or policy.require_target:
        return True
    return any(item.require or item.forbid or item.max_active is not None for item in policy.rules.values())


def _write_output(text: str, output: str | None) -> None:
    if output is None:
        print(text)
        return
    path = Path(output).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + ('\n' if not text.endswith('\n') else ''), encoding='utf-8')


def _run_check(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd).expanduser().resolve(strict=False)
    repo = _repo_path(cwd, _optional_path(args.repo))
    policy = load_policy(_optional_path(args.policy), repo)

    unknown_policy = sorted((set(policy.agents) | set(policy.rules)) - set(RESOLVERS))
    if unknown_policy:
        raise ValueError(f'policy references unsupported agent(s): {", ".join(unknown_policy)}')

    if args.agents:
        agents = _parse_agents(args.agents)
    elif policy.agents:
        agents = list(policy.agents)
    else:
        agents = sorted(RESOLVERS)

    cli_assertions = any(
        (args.require_instructions, args.fail_on_warnings, args.fail_on_divergence, args.require_target)
    )
    if not _policy_has_assertions(policy) and not cli_assertions:
        raise ValueError(
            'no check assertions configured; add .agentwhich.toml or pass a check flag such as --require-instructions'
        )

    results = [
        resolve(agent, cwd=cwd, repo=repo, target=_optional_path(args.target))
        for agent in agents
    ]
    report = evaluate_check(
        compare_results(results),
        policy,
        require_instructions=args.require_instructions,
        fail_on_warnings=args.fail_on_warnings,
        fail_on_divergence=args.fail_on_divergence,
        require_target=args.require_target,
    )
    if args.format == 'sarif':
        rendered = render_sarif(report, VERSION)
    else:
        rendered = render_check_report(report, args.format)
    _write_output(rendered, args.output)
    return 0 if report.passed else 1


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

        if args.command == 'check':
            return _run_check(args)

        agents = _parse_agents(args.agents)
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
