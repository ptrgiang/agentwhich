from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..model import ResolutionResult


class Resolver(Protocol):
    name: str

    def resolve(self, repo: Path, cwd: Path, target: Path | None = None) -> ResolutionResult:
        ...
