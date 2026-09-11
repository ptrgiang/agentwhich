from __future__ import annotations

import json
from pathlib import Path

from ..discovery import descendant_chain, layer, path_chain
from ..model import ACTIVE_PHASES, ResolutionResult
from ._imports import resolve_markdown_imports


class GeminiResolver:
    name = 'gemini'

    def resolve(self, repo: Path, cwd: Path, target: Path | None = None) -> ResolutionResult:
        result = ResolutionResult(agent=self.name, repository=repo, cwd=cwd, target=target)
        order = 1
        filenames = self._context_filenames(repo)

        for filename in filenames:
            global_file = Path.home() / '.gemini' / filename
            if global_file.is_file():
                result.layers.append(
                    layer(
                        agent=self.name,
                        path=global_file,
                        phase='startup',
                        scope='global',
                        reason='global Gemini context file',
                        order=order,
                    )
                )
                order += 1

        for directory in path_chain(repo, cwd):
            for filename in filenames:
                path = directory / filename
                if path.is_file():
                    scope = 'repository' if directory == repo else 'directory'
                    result.layers.append(
                        layer(
                            agent=self.name,
                            path=path,
                            phase='startup',
                            scope=scope,
                            reason=f'workspace context file in {directory}',
                            order=order,
                        )
                    )
                    order += 1

        if target is not None:
            for directory in descendant_chain(repo, cwd, target):
                for filename in filenames:
                    path = directory / filename
                    if path.is_file() and not self._has_path(result, path):
                        result.layers.append(
                            layer(
                                agent=self.name,
                                path=path,
                                phase='target',
                                scope='descendant',
                                reason='Gemini JIT context discovered on target path',
                                order=order,
                            )
                        )
                        order += 1
        else:
            for filename in filenames:
                for path in sorted(cwd.rglob(filename)) if cwd.is_dir() else []:
                    if not self._has_path(result, path):
                        result.layers.append(
                            layer(
                                agent=self.name,
                                path=path,
                                phase='lazy',
                                scope='descendant',
                                reason='Gemini JIT context candidate',
                            )
                        )

        roots = [item for item in result.layers if item.phase in ACTIVE_PHASES]
        imports, warnings = resolve_markdown_imports(
            self.name,
            roots,
            inline=True,
        )
        for imported in imports:
            result.layers.append(
                layer(
                    agent=self.name,
                    path=imported.path,
                    phase='import',
                    scope='import',
                    reason=imported.reason,
                    order=order,
                    note=imported.note,
                )
            )
            order += 1
        result.warnings.extend(warnings)
        return result

    def _context_filenames(self, repo: Path) -> list[str]:
        for settings in (repo / '.gemini' / 'settings.json', Path.home() / '.gemini' / 'settings.json'):
            names = self._read_context_names(settings)
            if names:
                return names
        return ['GEMINI.md']

    @staticmethod
    def _read_context_names(path: Path) -> list[str]:
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return []
        value = data.get('context', {}).get('fileName') if isinstance(data, dict) else None
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        if isinstance(value, list):
            return [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return []

    @staticmethod
    def _has_path(result: ResolutionResult, path: Path) -> bool:
        resolved = path.resolve(strict=False)
        return any(item.path == resolved for item in result.layers)
