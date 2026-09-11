from __future__ import annotations

import hashlib
from pathlib import Path

from .model import InstructionLayer

MAX_READ_BYTES = 1_000_000


def repository_root(start: Path) -> Path:
    current = start.expanduser().resolve(strict=False)
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / '.git').exists():
            return candidate
    return current


def path_chain(repo: Path, cwd: Path) -> list[Path]:
    repo = repo.resolve(strict=False)
    cwd = cwd.resolve(strict=False)
    try:
        relative = cwd.relative_to(repo)
    except ValueError as exc:
        raise ValueError(f'cwd {cwd} is outside repository {repo}') from exc

    chain = [repo]
    cursor = repo
    for part in relative.parts:
        cursor = cursor / part
        chain.append(cursor)
    return chain


def file_metadata(path: Path) -> tuple[int, int, str]:
    try:
        raw = path.read_bytes()
    except OSError:
        return 0, 0, ''
    byte_count = len(raw)
    digest = hashlib.sha256(raw).hexdigest()
    line_count = raw.count(b'\n') + (1 if raw and not raw.endswith(b'\n') else 0)
    return byte_count, line_count, digest


def layer(
    *,
    agent: str,
    path: Path,
    phase: str,
    scope: str,
    reason: str,
    order: int | None = None,
    selected: bool = True,
    note: str | None = None,
) -> InstructionLayer:
    byte_count, line_count, digest = file_metadata(path) if path.is_file() else (0, 0, '')
    return InstructionLayer(
        agent=agent,
        path=path.resolve(strict=False),
        phase=phase,  # type: ignore[arg-type]
        scope=scope,
        reason=reason,
        order=order,
        byte_count=byte_count,
        line_count=line_count,
        sha256=digest,
        selected=selected,
        note=note,
    )
