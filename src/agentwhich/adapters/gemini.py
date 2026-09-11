from __future__ import annotations

from pathlib import Path

from ..discovery import layer, path_chain
from ..model import ResolutionResult
from ._imports import resolve_markdown_imports


class GeminiResolver:
    name = 'gemini'

    def resolve(self, repo: Path, cwd: Path, target: Path | None = None) -> ResolutionResult:
        result = ResolutionResult(agent=self.name, repository=repo, cwd=cwd)
        order = 1

        global_file = Path.home() / '.gemini' / 'GEMINI.md'
        if global_file.is_file():
            result.layers.append(layer(agent=self.name, path=global_file, phase='startup', scope='global', reason='global Gemini context file', order=order))
            order += 1

        for directory in path_chain(repo, cwd):
            path = directory / 'GEMINI.md'
            if path.is_file():
                scope = 'repository' if directory == repo else 'directory'
                result.layers.append(layer(agent=self.name, path=path, phase='startup', scope=scope, reason=f'workspace context file in {directory}', order=order))
                order += 1

        imports, warnings = resolve_markdown_imports(self.name, list(result.layers))
        for imported in imports:
            result.layers.append(layer(agent=self.name, path=imported.path, phase='import', scope='import', reason=imported.reason, order=order))
            order += 1
        result.warnings.extend(warnings)

        for directory in cwd.iterdir() if cwd.is_dir() else []:
            if directory.is_dir():
                descendant = directory / 'GEMINI.md'
                if descendant.is_file():
                    result.layers.append(layer(agent=self.name, path=descendant, phase='lazy', scope='descendant', reason='just-in-time descendant context candidate'))

        if target is not None:
            result.warnings.append('Target-aware Gemini just-in-time context simulation is planned for v0.2.')
        return result
