from __future__ import annotations

import re
from pathlib import Path

from ..discovery import MAX_READ_BYTES, layer
from ..model import InstructionLayer

_IMPORT_RE = re.compile(r'^\s*@([^\s#]+)\s*$', re.MULTILINE)


def resolve_markdown_imports(agent: str, roots: list[InstructionLayer]) -> tuple[list[InstructionLayer], list[str]]:
    imported: list[InstructionLayer] = []
    warnings: list[str] = []
    visited: set[Path] = {item.path.resolve(strict=False) for item in roots}

    def walk(source: Path, depth: int) -> None:
        if depth > 12:
            warnings.append(f'import depth limit reached at {source}')
            return
        try:
            if source.stat().st_size > MAX_READ_BYTES:
                warnings.append(f'skipped import scan for large file: {source}')
                return
            text = source.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            return
        for match in _IMPORT_RE.finditer(text):
            raw = match.group(1).strip().strip('"\'')
            target = (source.parent / raw).expanduser().resolve(strict=False)
            if target in visited:
                continue
            visited.add(target)
            if not target.is_file():
                warnings.append(f'missing import referenced by {source.name}: {raw}')
                continue
            imported.append(layer(agent=agent, path=target, phase='import', scope='import', reason=f'imported by {source.name}'))
            walk(target, depth + 1)

    for root in roots:
        walk(root.path, 0)
    return imported, warnings
