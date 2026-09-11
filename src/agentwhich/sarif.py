from __future__ import annotations

import json
from pathlib import Path

from .checks import (
    RULE_DIVERGENCE,
    RULE_FORBIDDEN_ACTIVE,
    RULE_MAX_ACTIVE,
    RULE_MISSING_INSTRUCTIONS,
    RULE_REQUIRED_MISSING,
    RULE_TARGET_REQUIRED,
    RULE_WARNING,
    CheckReport,
    Violation,
)

RULES = {
    RULE_MISSING_INSTRUCTIONS: (
        'Missing repository instructions',
        'An agent has no active repository instruction files.',
    ),
    RULE_REQUIRED_MISSING: ('Required instruction missing', 'A policy-required instruction pattern did not match.'),
    RULE_FORBIDDEN_ACTIVE: ('Forbidden instruction active', 'An instruction forbidden by policy is active.'),
    RULE_MAX_ACTIVE: ('Too many active instructions', 'The active repository instruction count exceeds policy.'),
    RULE_WARNING: (
        'Resolver warning',
        'The resolver produced a warning and policy treats warnings as failures.',
    ),
    RULE_DIVERGENCE: ('Instruction sets diverge', 'Selected agents resolve different active instruction source sets.'),
    RULE_TARGET_REQUIRED: ('Target path required', 'The policy requires target-aware checking.'),
}


def _location(path: Path, repo: Path) -> dict[str, object] | None:
    try:
        rel = path.resolve(strict=False).relative_to(repo.resolve(strict=False)).as_posix()
    except ValueError:
        return None
    return {
        'physicalLocation': {
            'artifactLocation': {'uri': rel},
            'region': {'startLine': 1},
        }
    }


def _fallback_location(report: CheckReport) -> Path | None:
    if report.policy.path is not None:
        return report.policy.path
    for result in report.comparison.results:
        if result.target is not None and result.target.is_file():
            return result.target
        for layer in result.layers:
            try:
                layer.path.resolve(strict=False).relative_to(result.repository.resolve(strict=False))
            except ValueError:
                continue
            if layer.path.is_file():
                return layer.path
    return None


def _result(item: Violation, report: CheckReport) -> dict[str, object]:
    payload: dict[str, object] = {
        'ruleId': item.rule_id,
        'level': 'error',
        'message': {'text': item.message},
    }
    location_path = item.path or _fallback_location(report)
    if location_path is not None:
        location = _location(location_path, report.repository)
        if location is not None:
            payload['locations'] = [location]
    return payload


def to_sarif(report: CheckReport, version: str) -> dict[str, object]:
    rules = [
        {
            'id': rule_id,
            'name': title.replace(' ', ''),
            'shortDescription': {'text': title},
            'fullDescription': {'text': description},
            'defaultConfiguration': {'level': 'error'},
        }
        for rule_id, (title, description) in RULES.items()
    ]
    return {
        '$schema': 'https://json.schemastore.org/sarif-2.1.0.json',
        'version': '2.1.0',
        'runs': [
            {
                'tool': {
                    'driver': {
                        'name': 'agentwhich',
                        'version': version,
                        'informationUri': 'https://github.com/ptrgiang/agentwhich',
                        'rules': rules,
                    }
                },
                'results': [_result(item, report) for item in report.violations],
            }
        ],
    }


def render_sarif(report: CheckReport, version: str) -> str:
    return json.dumps(to_sarif(report, version), indent=2, ensure_ascii=False)
