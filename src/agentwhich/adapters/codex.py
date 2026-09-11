from __future__ import annotations

import os
import tomllib
from pathlib import Path

from ..discovery import layer, path_chain
from ..model import ResolutionResult


class CodexResolver:
    name = 'codex'

    def _codex_home(self) -> Path:
        return Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')).expanduser()

    def _fallback_names(self) -> list[str]:
        config = self._codex_home() / 'config.toml'
        if not config.is_file():
            return []
        try:
            data = tomllib.loads(config.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
            return []
        names = data.get('project_doc_fallback_filenames', [])
        if not isinstance(names, list):
            return []
        return [str(name) for name in names if isinstance(name, str) and name.strip()]

    def resolve(self, repo: Path, cwd: Path, target: Path | None = None) -> ResolutionResult:
        result = ResolutionResult(agent=self.name, repository=repo, cwd=cwd)
        order = 1

        global_dir = self._codex_home()
        global_candidates = [global_dir / 'AGENTS.override.md', global_dir / 'AGENTS.md']
        existing_global = [p for p in global_candidates if p.is_file()]
        if existing_global:
            chosen = existing_global[0]
            result.layers.append(layer(agent=self.name, path=chosen, phase='startup', scope='global', reason='global Codex instruction file', order=order))
            order += 1
            for skipped in existing_global[1:]:
                result.skipped.append(layer(agent=self.name, path=skipped, phase='startup', scope='global', reason=f'shadowed by {chosen.name}', selected=False))

        fallback_names = self._fallback_names()
        candidate_names = ['AGENTS.override.md', 'AGENTS.md', *fallback_names]
        for directory in path_chain(repo, cwd):
            existing = [directory / name for name in candidate_names if (directory / name).is_file()]
            if not existing:
                continue
            chosen = existing[0]
            scope = 'repository' if directory == repo else 'directory'
            result.layers.append(layer(agent=self.name, path=chosen, phase='startup', scope=scope, reason=f'selected in {directory}', order=order))
            order += 1
            for skipped in existing[1:]:
                result.skipped.append(layer(agent=self.name, path=skipped, phase='startup', scope=scope, reason=f'shadowed by {chosen.name} in the same directory', selected=False))

        if target is not None:
            result.warnings.append('Codex target-file simulation is not required for AGENTS.md startup resolution in v0.1.')
        return result
