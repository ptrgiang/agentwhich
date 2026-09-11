from __future__ import annotations

import os
import sys
from pathlib import Path

from ..discovery import descendant_chain, layer, path_chain
from ..model import ACTIVE_PHASES, ResolutionResult
from ._frontmatter import matches_any, read_frontmatter
from ._imports import resolve_markdown_imports


class ClaudeResolver:
    name = 'claude'

    def resolve(self, repo: Path, cwd: Path, target: Path | None = None) -> ResolutionResult:
        result = ResolutionResult(agent=self.name, repository=repo, cwd=cwd, target=target)
        order = 1

        for managed in self._managed_policy_candidates():
            if managed.is_file():
                result.layers.append(
                    layer(
                        agent=self.name,
                        path=managed,
                        phase='startup',
                        scope='managed',
                        reason='organization-managed Claude instruction file',
                        order=order,
                    )
                )
                order += 1

        global_file = Path.home() / '.claude' / 'CLAUDE.md'
        if global_file.is_file():
            result.layers.append(
                layer(
                    agent=self.name,
                    path=global_file,
                    phase='startup',
                    scope='global',
                    reason='user-level Claude instruction file',
                    order=order,
                )
            )
            order += 1

        for directory in path_chain(repo, cwd):
            candidates = [directory / 'CLAUDE.md', directory / 'CLAUDE.local.md']
            if directory == repo:
                candidates.insert(1, directory / '.claude' / 'CLAUDE.md')
            for path in candidates:
                if path.is_file():
                    scope = 'repository' if directory == repo else 'directory'
                    result.layers.append(
                        layer(
                            agent=self.name,
                            path=path,
                            phase='startup',
                            scope=scope,
                            reason=f'ancestor instruction file in {directory}',
                            order=order,
                        )
                    )
                    order += 1

        order = self._add_rules(result, Path.home() / '.claude' / 'rules', target, order, 'user-rule')
        order = self._add_rules(result, repo / '.claude' / 'rules', target, order, 'rule')

        if target is not None:
            for directory in descendant_chain(repo, cwd, target):
                for filename in ('CLAUDE.md', 'CLAUDE.local.md'):
                    path = directory / filename
                    if path.is_file() and not self._has_path(result, path):
                        result.layers.append(
                            layer(
                                agent=self.name,
                                path=path,
                                phase='target',
                                scope='descendant',
                                reason='descendant instruction loaded when Claude reads the target subtree',
                                order=order,
                            )
                        )
                        order += 1
        else:
            for path in self._descendant_memories(cwd):
                if not self._has_path(result, path):
                    result.layers.append(
                        layer(
                            agent=self.name,
                            path=path,
                            phase='lazy',
                            scope='descendant',
                            reason='descendant instruction candidate; loads when Claude reads that subtree',
                        )
                    )

        memory_roots = [
            item
            for item in result.layers
            if item.phase in ACTIVE_PHASES and item.path.name in {'CLAUDE.md', 'CLAUDE.local.md'}
        ]
        imports, warnings = resolve_markdown_imports(
            self.name,
            memory_roots,
            max_depth=4,
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

    def _add_rules(
        self,
        result: ResolutionResult,
        root: Path,
        target: Path | None,
        order: int,
        scope: str,
    ) -> int:
        if not root.is_dir():
            return order
        for path in sorted(root.rglob('*.md')):
            patterns = read_frontmatter(path).get('paths', [])
            if not patterns:
                result.layers.append(
                    layer(
                        agent=self.name,
                        path=path,
                        phase='startup',
                        scope=scope,
                        reason='unconditional Claude rule (no paths frontmatter)',
                        order=order,
                    )
                )
                order += 1
                continue
            if target is None:
                result.layers.append(
                    layer(
                        agent=self.name,
                        path=path,
                        phase='lazy',
                        scope=scope,
                        reason=f'path-scoped Claude rule: {", ".join(patterns)}',
                    )
                )
                continue
            if matches_any(target, result.repository, patterns):
                result.layers.append(
                    layer(
                        agent=self.name,
                        path=path,
                        phase='target',
                        scope=scope,
                        reason=f'paths frontmatter matches target: {", ".join(patterns)}',
                        order=order,
                    )
                )
                order += 1
            else:
                result.skipped.append(
                    layer(
                        agent=self.name,
                        path=path,
                        phase='target',
                        scope=scope,
                        reason=f'paths frontmatter does not match target: {", ".join(patterns)}',
                        selected=False,
                    )
                )
        return order

    def _descendant_memories(self, cwd: Path) -> list[Path]:
        found: set[Path] = set()
        if not cwd.is_dir():
            return []
        for filename in ('CLAUDE.md', 'CLAUDE.local.md'):
            found.update(path.resolve(strict=False) for path in cwd.rglob(filename))
        return sorted(found)

    def _managed_policy_candidates(self) -> list[Path]:
        if os.name == 'nt':
            return [Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'ClaudeCode' / 'CLAUDE.md']
        if sys.platform == 'darwin':
            return [Path('/Library/Application Support/ClaudeCode/CLAUDE.md')]
        return [Path('/etc/claude-code/CLAUDE.md')]

    @staticmethod
    def _has_path(result: ResolutionResult, path: Path) -> bool:
        resolved = path.resolve(strict=False)
        return any(item.path == resolved for item in result.layers)
