from __future__ import annotations

import re
from pathlib import Path

from ..discovery import MAX_READ_BYTES


def read_frontmatter(path: Path) -> dict[str, list[str]]:
    try:
        if path.stat().st_size > MAX_READ_BYTES:
            return {}
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return {}
    if not text.startswith('---'):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return {}
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == '---')
    except StopIteration:
        return {}

    result: dict[str, list[str]] = {}
    current: str | None = None
    for raw in lines[1:end]:
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('- ') and current:
            result.setdefault(current, []).append(_unquote(line[2:].strip()))
            continue
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        current = key.strip()
        value = value.strip()
        if not value:
            result.setdefault(current, [])
            continue
        if value.startswith('[') and value.endswith(']'):
            items = [part.strip() for part in value[1:-1].split(',') if part.strip()]
            result[current] = [_unquote(item) for item in items]
        else:
            result[current] = [_unquote(value)]
    return result


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def brace_expand(pattern: str, limit: int = 1000) -> list[str]:
    results = [pattern]
    brace_re = re.compile(r'\{([^{}]+)\}')
    while True:
        expanded: list[str] = []
        changed = False
        for item in results:
            match = brace_re.search(item)
            if not match:
                expanded.append(item)
                continue
            changed = True
            choices = [part for part in match.group(1).split(',') if part]
            if len(expanded) + len(choices) > limit:
                return [pattern]
            for choice in choices:
                expanded.append(item[: match.start()] + choice + item[match.end() :])
        results = expanded
        if not changed:
            return results


def matches_any(target: Path, repo: Path, patterns: list[str]) -> bool:
    try:
        rel = target.resolve(strict=False).relative_to(repo.resolve(strict=False)).as_posix()
    except ValueError:
        return False
    for pattern in patterns:
        for expanded in brace_expand(pattern.strip()):
            normalized = expanded.removeprefix('./')
            if re.fullmatch(_glob_regex(normalized), rel):
                return True
    return False


def _glob_regex(pattern: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == '*':
            if index + 1 < len(pattern) and pattern[index + 1] == '*':
                index += 2
                if index < len(pattern) and pattern[index] == '/':
                    out.append('(?:.*/)?')
                    index += 1
                else:
                    out.append('.*')
                continue
            out.append('[^/]*')
        elif char == '?':
            out.append('[^/]')
        elif char == '[':
            end = pattern.find(']', index + 1)
            if end == -1:
                out.append(r'\[')
            else:
                content = pattern[index + 1 : end]
                if content.startswith('!'):
                    content = '^' + content[1:]
                out.append('[' + content + ']')
                index = end
        else:
            out.append(re.escape(char))
        index += 1
    return ''.join(out)
