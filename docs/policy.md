# Policy checks

`agentwhich check` converts instruction discovery into deterministic assertions suitable for local scripts and CI.

## Policy file

The default policy path is `.agentwhich.toml` at the repository root.

```toml
version = 1
agents = ["codex", "claude", "gemini", "copilot"]
require_instructions = false
fail_on_warnings = false
fail_on_divergence = false
require_target = false

[rules.codex]
require = ["AGENTS.md"]
forbid = ["**/AGENTS.override.md"]
max_active = 4
```

### Top-level fields

- `version`: policy schema version. v0.3 supports `1`.
- `agents`: agents checked when `--agents` is not supplied.
- `require_instructions`: require at least one active repository-local instruction file for every selected agent.
- `fail_on_warnings`: convert resolver warnings into violations.
- `fail_on_divergence`: fail when selected agents resolve different active source-path sets.
- `require_target`: fail unless `--target` is supplied.

### Per-agent rules

Use `[rules.<agent>]` for `codex`, `claude`, `gemini`, or `copilot`.

- `require`: every glob must match at least one active repository-local instruction file.
- `forbid`: every active repository-local instruction matching a glob is a violation.
- `max_active`: maximum number of active repository-local instruction files.

Policy paths are repository-relative. Glob behavior is path-aware:

- `*` matches within one path segment.
- `**` crosses directories.
- `?` matches one non-separator character.
- `{a,b}` expands alternatives.

Examples:

```toml
[rules.claude]
require = ["CLAUDE.md", ".claude/rules/**/*.md"]
forbid = ["**/CLAUDE.local.md"]

[rules.copilot]
require = [".github/copilot-instructions.md"]
forbid = [".github/instructions/legacy-*.instructions.md"]
```

## CLI-only assertions

You can use checks without a policy file:

```bash
agentwhich check --agents codex,claude --require-instructions
agentwhich check --agents codex,claude --fail-on-divergence
agentwhich check --agents claude --target src/api.py --fail-on-warnings
```

CLI flags only make the check stricter; they do not disable assertions present in the policy file.

## Rule IDs

| Rule | Meaning |
| --- | --- |
| `AW001` | Selected agent has no active repository instruction files. |
| `AW002` | A required instruction glob did not match. |
| `AW003` | A forbidden instruction is active. |
| `AW004` | Active repository instruction count exceeds `max_active`. |
| `AW005` | Resolver warning treated as a failure. |
| `AW006` | Active source sets diverge across selected agents. |
| `AW007` | Policy requires a target but none was supplied. |

These IDs are also used in SARIF output.

## Exit codes

- `0`: pass.
- `1`: one or more policy violations.
- `2`: invalid command, unsupported agent, or policy/configuration error.

## SARIF

```bash
agentwhich check --format sarif --output agentwhich.sarif
```

SARIF output uses version 2.1.0. Violations are attached to the offending instruction file when one exists; policy-level and missing-file violations are attached to `.agentwhich.toml` when a policy file is present.

## Determinism

Policy matching intentionally ignores active files outside the repository, such as `~/.claude/CLAUDE.md` or `~/.codex/AGENTS.md`. Those files still appear in `explain` and `compare`, but they do not make a repository policy pass or fail differently from one machine to another.
