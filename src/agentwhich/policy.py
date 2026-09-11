from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

POLICY_FILENAME = '.agentwhich.toml'


@dataclass(frozen=True, slots=True)
class AgentPolicy:
    require: tuple[str, ...] = ()
    forbid: tuple[str, ...] = ()
    max_active: int | None = None


@dataclass(frozen=True, slots=True)
class Policy:
    path: Path | None = None
    agents: tuple[str, ...] = ()
    require_instructions: bool = False
    fail_on_warnings: bool = False
    fail_on_divergence: bool = False
    require_target: bool = False
    rules: dict[str, AgentPolicy] = field(default_factory=dict)


def _string_list(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f'{field_name} must be an array of non-empty strings')
    return tuple(item.strip() for item in value)


def _bool(value: object, field_name: str, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f'{field_name} must be true or false')
    return value


def load_policy(path: Path | str | None, repo: Path) -> Policy:
    repo = repo.expanduser().resolve(strict=False)
    if path is None:
        candidate = repo / POLICY_FILENAME
        if not candidate.is_file():
            return Policy()
    else:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = repo / candidate
        candidate = candidate.resolve(strict=False)
        if not candidate.is_file():
            raise ValueError(f'policy file not found: {candidate}')

    try:
        data = tomllib.loads(candidate.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f'cannot read policy file {candidate}: {exc}') from exc

    allowed_top = {
        'version',
        'agents',
        'require_instructions',
        'fail_on_warnings',
        'fail_on_divergence',
        'require_target',
        'rules',
    }
    unknown_top = sorted(set(data) - allowed_top)
    if unknown_top:
        raise ValueError(f'unknown policy field(s): {", ".join(unknown_top)}')

    version = data.get('version', 1)
    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
        raise ValueError(f'unsupported policy version {version!r}; expected 1')

    agents = tuple(dict.fromkeys(_string_list(data.get('agents'), 'agents')))
    rules_raw = data.get('rules', {})
    if not isinstance(rules_raw, dict):
        raise ValueError('rules must be a TOML table')

    rules: dict[str, AgentPolicy] = {}
    for agent, raw in rules_raw.items():
        if not isinstance(raw, dict):
            raise ValueError(f'rules.{agent} must be a TOML table')
        allowed_rule = {'require', 'forbid', 'max_active'}
        unknown_rule = sorted(set(raw) - allowed_rule)
        if unknown_rule:
            names = ', '.join(unknown_rule)
            raise ValueError(f'unknown rules.{agent} field(s): {names}')
        max_active = raw.get('max_active')
        if max_active is not None and (
            not isinstance(max_active, int) or isinstance(max_active, bool) or max_active < 0
        ):
            raise ValueError(f'rules.{agent}.max_active must be a non-negative integer')
        rules[str(agent).lower()] = AgentPolicy(
            require=_string_list(raw.get('require'), f'rules.{agent}.require'),
            forbid=_string_list(raw.get('forbid'), f'rules.{agent}.forbid'),
            max_active=max_active,
        )

    return Policy(
        path=candidate,
        agents=tuple(agent.lower() for agent in agents),
        require_instructions=_bool(data.get('require_instructions'), 'require_instructions'),
        fail_on_warnings=_bool(data.get('fail_on_warnings'), 'fail_on_warnings'),
        fail_on_divergence=_bool(data.get('fail_on_divergence'), 'fail_on_divergence'),
        require_target=_bool(data.get('require_target'), 'require_target'),
        rules=rules,
    )
