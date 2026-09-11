from __future__ import annotations

from pathlib import Path

from .adapters import RESOLVERS
from .discovery import repository_root
from .model import ResolutionResult


def resolve(agent: str, cwd: Path | str = '.', repo: Path | str | None = None, target: Path | str | None = None) -> ResolutionResult:
    agent = agent.lower().strip()
    if agent not in RESOLVERS:
        supported = ', '.join(sorted(RESOLVERS))
        raise ValueError(f'unsupported agent {agent!r}; choose one of: {supported}')

    cwd_path = Path(cwd).expanduser().resolve(strict=False)
    repo_path = Path(repo).expanduser().resolve(strict=False) if repo is not None else repository_root(cwd_path)
    target_path = Path(target).expanduser().resolve(strict=False) if target is not None else None
    return RESOLVERS[agent].resolve(repo=repo_path, cwd=cwd_path, target=target_path)
