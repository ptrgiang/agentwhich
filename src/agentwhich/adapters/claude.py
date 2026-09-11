from __future__ import annotations

from pathlib import Path

from ..discovery import layer, path_chain
from ..model import ResolutionResult
from ._imports import resolve_markdown_imports


class ClaudeResolver:
    name = 'claude'

    def resolve(self, repo: Path, cwd: Path, target: Path | None = None) -> ResolutionResult:
        result = ResolutionResult(agent=self.name, repository=repo, cwd=cwd)
        order = 1

        global_file = Path.home() / '.claude' / 'CLAUDE.md'
        if global_file.is_file():
            result.layers.append(layer(agent=self.name, path=global_file, phase='startup', scope='global', reason='user-level Claude instruction file', order=order))
            order += 1

        for directory in path_chain(repo, cwd):
            for filename in ('CLAUDE.md', 'CLAUDE.local.md'):
                path = directory / filename
                if path.is_file():
                    scope = 'repository' if directory == repo else 'directory'
                    result.layers.append(layer(agent=self.name, path=path, phase='startup', scope=scope, reason=f'ancestor instruction file in {directory}', order=order))
                    order += 1

        imports, warnings = resolve_markdown_imports(self.name, list(result.layers))
        for imported in imports:
            result.layers.append(layer(agent=self.name, path=imported.path, phase='import', scope='import', reason=imported.reason, order=order))
            order += 1
        result.warnings.extend(warnings)

        rules_root = repo / '.claude' / 'rules'
        if rules_root.is_dir():
            for path in sorted(rules_root.rglob('*.md')):
                result.layers.append(layer(agent=self.name, path=path, phase='lazy', scope='rule', reason='Claude rule candidate; applicability may depend on target path'))

        for directory in cwd.iterdir() if cwd.is_dir() else []:
            if directory.is_dir():
                descendant = directory / 'CLAUDE.md'
                if descendant.is_file():
                    result.layers.append(layer(agent=self.name, path=descendant, phase='lazy', scope='descendant', reason='descendant instruction candidate; loaded when Claude works in that subtree'))

        if target is not None:
            result.warnings.append('Target-aware Claude path rule evaluation is planned for v0.2; candidates are shown conservatively in v0.1.')
        return result
