from __future__ import annotations

import re
from pathlib import Path

from ..discovery import MAX_READ_BYTES, layer
from ..model import InstructionLayer

_TOKEN_RE = re.compile(r'(?<!`)@([^\s`]+)')


def _strip_fenced_code(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    fence: str | None = None
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('```') or stripped.startswith('~~~'):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            out.append('\n')
            continue
        out.append('\n' if fence else line)
    return ''.join(out)


def _import_tokens(text: str, *, inline: bool) -> list[str]:
    text = _strip_fenced_code(text)
    if not inline:
        tokens: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith('@') and len(stripped.split()) == 1:
                tokens.append(stripped[1:])
        return tokens

    tokens = []
    for line in text.splitlines():
        cleaned = re.sub(r'`[^`]*`', '', line)
        tokens.extend(match.group(1) for match in _TOKEN_RE.finditer(cleaned))
    return tokens


def resolve_markdown_imports(
    agent: str,
    roots: list[InstructionLayer],
    *,
    max_depth: int = 12,
    inline: bool = False,
    allowed_roots: tuple[Path, ...] | None = None,
) -> tuple[list[InstructionLayer], list[str]]:
    imported: list[InstructionLayer] = []
    warnings: list[str] = []
    visited: set[Path] = {item.path.resolve(strict=False) for item in roots}

    def walk(source: Path, depth: int) -> None:
        if depth >= max_depth:
            warnings.append(f'import depth limit reached at {source}')
            return
        try:
            if source.stat().st_size > MAX_READ_BYTES:
                warnings.append(f'skipped import scan for large file: {source}')
                return
            text = source.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            return
        for raw in _import_tokens(text, inline=inline):
            raw = raw.strip().strip('"\'').rstrip('.,;:)')
            candidate = Path(raw).expanduser()
            target = candidate if candidate.is_absolute() else source.parent / candidate
            target = target.resolve(strict=False)
            if allowed_roots is not None:
                if not any(_is_within(target, root) for root in allowed_roots):
                    warnings.append(f'blocked import outside allowed roots from {source.name}: {raw}')
                    continue
            if target in visited:
                continue
            visited.add(target)
            if not target.is_file():
                warnings.append(f'missing import referenced by {source.name}: {raw}')
                continue
            imported.append(
                layer(
                    agent=agent,
                    path=target,
                    phase='import',
                    scope='import',
                    reason=f'imported by {source.name}',
                    note=f'source={source}',
                )
            )
            walk(target, depth + 1)

    for root in roots:
        walk(root.path, 0)
    return imported, warnings


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False
