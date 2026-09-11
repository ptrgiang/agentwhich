from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Phase = Literal['startup', 'import', 'lazy', 'target', 'unknown']


@dataclass(frozen=True, slots=True)
class InstructionLayer:
    agent: str
    path: Path
    phase: Phase
    scope: str
    reason: str
    order: int | None = None
    byte_count: int = 0
    line_count: int = 0
    sha256: str = ''
    selected: bool = True
    note: str | None = None

    def to_dict(self, repo: Path | None = None) -> dict[str, object]:
        data = asdict(self)
        data['path'] = display_path(self.path, repo)
        return data


@dataclass(slots=True)
class ResolutionResult:
    agent: str
    repository: Path
    cwd: Path
    layers: list[InstructionLayer] = field(default_factory=list)
    skipped: list[InstructionLayer] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            'schema_version': 1,
            'agent': self.agent,
            'repository': str(self.repository),
            'cwd': str(self.cwd),
            'layers': [layer.to_dict(self.repository) for layer in self.layers],
            'skipped': [layer.to_dict(self.repository) for layer in self.skipped],
            'warnings': self.warnings,
        }


def display_path(path: Path, repo: Path | None = None) -> str:
    path = path.expanduser().resolve(strict=False)
    if repo is not None:
        repo = repo.expanduser().resolve(strict=False)
        try:
            rel = path.relative_to(repo)
            return '.' if str(rel) == '.' else f'./{rel.as_posix()}'
        except ValueError:
            pass
    try:
        rel_home = path.relative_to(Path.home().resolve(strict=False))
        return '~' if str(rel_home) == '.' else f'~/{rel_home.as_posix()}'
    except ValueError:
        return str(path)
