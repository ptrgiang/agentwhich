from __future__ import annotations

import io
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True, slots=True)
class ChangedFile:
    status: str
    old_path: str | None
    new_path: str | None

    @property
    def path(self) -> str:
        return self.new_path or self.old_path or ''


def _git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    if shutil.which('git') is None:
        raise ValueError('git executable is required for ref-aware commands')
    command = ['git', '-C', str(repo), *args]
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise ValueError(f'cannot run git: {exc}') from exc
    if completed.returncode != 0:
        message = completed.stderr.decode('utf-8', errors='replace').strip()
        raise ValueError(f'git {" ".join(args)} failed: {message or "unknown git error"}')
    if binary:
        return completed.stdout
    return completed.stdout.decode('utf-8', errors='strict').strip()


def git_root(repo: Path) -> Path:
    root = Path(str(_git(repo, 'rev-parse', '--show-toplevel'))).resolve(strict=False)
    requested = repo.resolve(strict=False)
    if root != requested:
        raise ValueError(f'repository {requested} is not the Git root {root}')
    return root


def resolve_ref(repo: Path, ref: str) -> str:
    if not ref or ref.startswith('-'):
        raise ValueError(f'invalid Git ref: {ref!r}')
    return str(_git(repo, 'rev-parse', '--verify', f'{ref}^{{commit}}'))


def merge_base(repo: Path, base: str, head: str) -> str:
    return str(_git(repo, 'merge-base', base, head))


def changed_files(repo: Path, base_commit: str, head_commit: str) -> list[ChangedFile]:
    raw = _git(
        repo,
        'diff',
        '--name-status',
        '-z',
        '--find-renames',
        base_commit,
        head_commit,
        '--',
        binary=True,
    )
    assert isinstance(raw, bytes)
    tokens = raw.split(b'\0')
    if tokens and not tokens[-1]:
        tokens.pop()

    result: list[ChangedFile] = []
    index = 0
    while index < len(tokens):
        status = tokens[index].decode('utf-8', errors='surrogateescape')
        index += 1
        kind = status[:1]
        if kind in {'R', 'C'}:
            if index + 1 >= len(tokens):
                raise ValueError('unexpected git diff output for renamed/copied path')
            old_path = tokens[index].decode('utf-8', errors='surrogateescape')
            new_path = tokens[index + 1].decode('utf-8', errors='surrogateescape')
            index += 2
        else:
            if index >= len(tokens):
                raise ValueError('unexpected git diff output for changed path')
            path = tokens[index].decode('utf-8', errors='surrogateescape')
            index += 1
            old_path = None if kind == 'A' else path
            new_path = None if kind == 'D' else path
        result.append(ChangedFile(status=status, old_path=old_path, new_path=new_path))
    return result


def within_scope(path: str | None, scope: str) -> bool:
    if path is None:
        return False
    if not scope or scope == '.':
        return True
    normalized_scope = scope.strip('/')
    return path == normalized_scope or path.startswith(normalized_scope + '/')


def materialize_ref(repo: Path, ref: str, destination: Path) -> None:
    raw = _git(repo, 'archive', '--format=tar', ref, binary=True)
    assert isinstance(raw, bytes)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive.getmembers():
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError(f'unsafe path in git archive: {member.name!r}')
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            source = archive.extractfile(member)
            if source is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('wb') as output:
                shutil.copyfileobj(source, output)
