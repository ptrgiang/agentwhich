from __future__ import annotations

import os
from pathlib import Path

from ..discovery import descendant_chain, layer, path_chain
from ..model import ACTIVE_PHASES, InstructionLayer, ResolutionResult
from ._frontmatter import matches_any, read_frontmatter
from ._imports import resolve_markdown_imports


class CopilotResolver:
    name = 'copilot'

    def resolve(self, repo: Path, cwd: Path, target: Path | None = None) -> ResolutionResult:
        result = ResolutionResult(agent=self.name, repository=repo, cwd=cwd, target=target)
        order = 1

        personal = Path.home() / '.copilot' / 'copilot-instructions.md'
        if personal.is_file():
            result.layers.append(
                layer(
                    agent=self.name,
                    path=personal,
                    phase='startup',
                    scope='global',
                    reason='personal Copilot CLI instructions',
                    order=order,
                )
            )
            order += 1

        order = self._add_modular_rules(
            result,
            Path.home() / '.copilot' / 'instructions',
            target,
            order,
            'global-rule',
        )

        startup_dirs = path_chain(repo, cwd)
        for directory in startup_dirs:
            order = self._add_standard_files(result, directory, 'startup', order)

        # GitHub documents modular repository rules in the repository root and cwd,
        # but not in intermediate directories.
        modular_roots: list[Path] = [repo]
        if cwd.resolve(strict=False) != repo.resolve(strict=False):
            modular_roots.append(cwd)
        for directory in modular_roots:
            order = self._add_modular_rules(
                result,
                directory / '.github' / 'instructions',
                target,
                order,
                'rule',
            )

        if target is not None:
            for directory in descendant_chain(repo, cwd, target):
                order = self._add_standard_files(result, directory, 'target', order)
                order = self._add_modular_rules(
                    result,
                    directory / '.github' / 'instructions',
                    target,
                    order,
                    'rule',
                )

        custom_dirs = self._custom_instruction_dirs()
        for custom_dir in custom_dirs:
            path = custom_dir / 'AGENTS.md'
            if path.is_file():
                result.layers.append(
                    layer(
                        agent=self.name,
                        path=path,
                        phase='startup',
                        scope='custom-dir',
                        reason='AGENTS.md from COPILOT_CUSTOM_INSTRUCTIONS_DIRS',
                        order=order,
                    )
                )
                order += 1
            order = self._add_modular_rules(result, custom_dir, target, order, 'custom-dir')

        import_roots = [
            item
            for item in result.layers
            if item.phase in ACTIVE_PHASES and self._supports_imports(item.path)
        ]
        allowed = (repo.resolve(strict=False), Path.home() / '.copilot', *custom_dirs)
        imports, warnings = resolve_markdown_imports(
            self.name,
            import_roots,
            inline=True,
            allowed_roots=allowed,
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
        self._dedupe_identical(result)
        return result

    def _add_standard_files(
        self,
        result: ResolutionResult,
        directory: Path,
        phase: str,
        order: int,
    ) -> int:
        candidates = [
            directory / '.github' / 'copilot-instructions.md',
            directory / 'AGENTS.md',
            directory / 'CLAUDE.md',
            directory / '.claude' / 'CLAUDE.md',
            directory / 'GEMINI.md',
        ]
        for path in candidates:
            if path.is_file() and not self._has_path(result, path):
                result.layers.append(
                    layer(
                        agent=self.name,
                        path=path,
                        phase=phase,
                        scope='repository' if directory == result.repository else 'directory',
                        reason='Copilot CLI combines applicable instruction files; no general precedence is defined',
                        order=order,
                    )
                )
                order += 1
        return order

    def _add_modular_rules(
        self,
        result: ResolutionResult,
        root: Path,
        target: Path | None,
        order: int,
        scope: str,
    ) -> int:
        if not root.is_dir():
            return order
        for path in sorted(root.rglob('*.instructions.md')):
            if self._has_path(result, path):
                continue
            patterns = read_frontmatter(path).get('applyTo', [])
            split_patterns = [part.strip() for value in patterns for part in value.split(',') if part.strip()]
            if not split_patterns:
                result.layers.append(
                    layer(
                        agent=self.name,
                        path=path,
                        phase='startup',
                        scope=scope,
                        reason='modular Copilot instruction without applyTo',
                        order=order,
                    )
                )
                order += 1
            elif target is None:
                result.layers.append(
                    layer(
                        agent=self.name,
                        path=path,
                        phase='lazy',
                        scope=scope,
                        reason=f'path-specific Copilot instruction: {", ".join(split_patterns)}',
                    )
                )
            elif matches_any(target, result.repository, split_patterns):
                result.layers.append(
                    layer(
                        agent=self.name,
                        path=path,
                        phase='target',
                        scope=scope,
                        reason=f'applyTo matches target: {", ".join(split_patterns)}',
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
                        reason=f'applyTo does not match target: {", ".join(split_patterns)}',
                        selected=False,
                    )
                )
        return order

    def _custom_instruction_dirs(self) -> list[Path]:
        raw = os.environ.get('COPILOT_CUSTOM_INSTRUCTIONS_DIRS', '')
        return [Path(item.strip()).expanduser() for item in raw.split(',') if item.strip()]

    @staticmethod
    def _supports_imports(path: Path) -> bool:
        return path.name in {'AGENTS.md', 'CLAUDE.md', 'copilot-instructions.md'}

    @staticmethod
    def _has_path(result: ResolutionResult, path: Path) -> bool:
        resolved = path.resolve(strict=False)
        return any(item.path == resolved for item in result.layers)

    def _dedupe_identical(self, result: ResolutionResult) -> None:
        seen: dict[str, InstructionLayer] = {}
        kept: list[InstructionLayer] = []
        for item in result.layers:
            if item.phase not in ACTIVE_PHASES or not item.sha256:
                kept.append(item)
                continue
            prior = seen.get(item.sha256)
            if prior is None:
                seen[item.sha256] = item
                kept.append(item)
                continue
            result.skipped.append(
                layer(
                    agent=self.name,
                    path=item.path,
                    phase=item.phase,
                    scope=item.scope,
                    reason=f'identical content deduplicated against {prior.path.name}',
                    selected=False,
                )
            )
        result.layers = kept
