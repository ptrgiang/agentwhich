# agentwhich

Inspect, diff, and enforce AI coding-agent instructions.

`agentwhich` answers a deceptively hard question: **what instruction files will this coding agent actually see here?**
It stays offline and read-only: no LLM, no API key, no network, no telemetry, and no Python runtime dependencies.

## Supported agents

| Agent | Startup hierarchy | Imports | Target/path rules | JIT/descendant context |
| --- | --- | --- | --- | --- |
| Codex | ✅ | n/a | n/a | n/a |
| Claude Code | ✅ | ✅ | ✅ `.claude/rules/**` | ✅ nested `CLAUDE.md` |
| Gemini CLI | ✅ | ✅ | configurable context names | ✅ target-path `GEMINI.md` |
| GitHub Copilot CLI | ✅ | ✅ supported files | ✅ `*.instructions.md` | ✅ target-path agent files |

## Install

```bash
python -m pip install -e ".[dev]"
```

## Explain one agent

```bash
agentwhich explain --agent claude --cwd . --target src/api/handler.ts
```

Phases are explicit:

- `startup`: loaded when the session starts.
- `import`: recursively referenced by an active instruction file.
- `target`: becomes active because the supplied target path matches or triggers it.
- `lazy`: known candidate whose applicability cannot be established without a target.
- `unknown`: intentionally unresolved rather than guessed.

## Compare agents

```bash
agentwhich compare \
  --cwd . \
  --target src/api/handler.ts \
  --agents codex,claude,gemini,copilot
```

Use `--format json` for scripts and CI.

## See what a PR changed

v0.4 adds Git-aware impact analysis without checking out or mutating either ref:

```bash
agentwhich changed \
  --base origin/main \
  --head HEAD \
  --agents codex,claude,gemini,copilot
```

`changed` uses the merge base of `--base` and `--head`, matching normal pull-request semantics. It evaluates only changed paths and reports instruction layers that were added, removed, content-changed, phase-changed, or reordered.

A changed instruction source whose full scope cannot be proven is reported separately as **potential broader impact**. It is not silently promoted to confirmed impact.

Use it as a CI gate only when desired:

```bash
agentwhich changed --base origin/main --head HEAD --fail-on-impact
```

Exit codes:

- `0`: no confirmed impact, or impact is only being reported.
- `1`: confirmed impact was found and `--fail-on-impact` was supplied.
- `2`: Git, configuration, or usage error.

For monorepos, point `--cwd` at one package to scope both changed paths and startup hierarchy:

```bash
agentwhich changed \
  --cwd services/payments \
  --base origin/main \
  --head HEAD
```

The default limit is 200 changed paths. Narrow `--cwd` or use `--max-targets 0` to disable the limit.

## Snapshot effective context

Emit a deterministic, repository-local context snapshot with path, phase, order, and SHA-256 for each active layer:

```bash
agentwhich snapshot --target src/api/handler.ts --format json
```

Snapshot a historical Git ref without checking it out:

```bash
agentwhich snapshot \
  --ref v0.3.0 \
  --target src/api/handler.ts \
  --output agentwhich-snapshot.json
```

Repeat `--target` to capture multiple target paths. When no target is provided, `snapshot` captures startup context.

Git is required only for `changed` and `snapshot --ref`. The Python package itself still has zero runtime dependencies.
See [`docs/impact.md`](docs/impact.md) for ref semantics, monorepo usage, and limitations.

## Enforce a policy

Create `.agentwhich.toml`:

```toml
version = 1
agents = ["codex", "claude", "gemini", "copilot"]
require_instructions = true
fail_on_warnings = true

[rules.codex]
require = ["AGENTS.md"]
forbid = ["**/AGENTS.override.md"]
max_active = 4

[rules.claude]
require = ["CLAUDE.md"]
forbid = ["**/CLAUDE.local.md"]
```

Then run:

```bash
agentwhich check --cwd .
```

Policy exit codes are intentionally CI-friendly:

- `0`: policy passed.
- `1`: policy violation.
- `2`: configuration or usage error.

Policy checks only repository-local active instruction files, so a developer's global agent configuration does not make CI nondeterministic.
See [`docs/policy.md`](docs/policy.md) for the complete policy schema.

## SARIF

Generate SARIF 2.1.0 for GitHub Code Scanning or another compatible consumer:

```bash
agentwhich check \
  --policy .agentwhich.toml \
  --format sarif \
  --output agentwhich.sarif
```

## GitHub Action

The repository is also a composite GitHub Action for policy enforcement. It can generate SARIF, optionally upload it, and fail the job after policy violations are reported.

```yaml
name: agentwhich

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write

jobs:
  instruction-policy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ptrgiang/agentwhich@v0.4.0
        with:
          policy: .agentwhich.toml
          upload-sarif: 'true'
```

For PR impact analysis, fetch Git history and run the CLI after installation:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
- uses: ptrgiang/agentwhich@v0.4.0
  with:
    policy: .agentwhich.toml
    upload-sarif: 'false'
- run: agentwhich changed --base "${{ github.event.pull_request.base.sha }}" --head HEAD
```

## v0.4 highlights

- `agentwhich snapshot` for deterministic repo-local context snapshots.
- Historical snapshots from any Git ref without checkout.
- `agentwhich changed` with merge-base PR semantics.
- Changed-file-aware target evaluation with content, phase, and ordering diffs.
- Conservative reporting of instruction-source changes whose broader scope cannot be proven.
- `--cwd` scoping for monorepo/package workflows.
- Optional `--fail-on-impact` CI gate and configurable target cap.

## Design rules

1. **Read-only.** Never checkout, rewrite, or mutate the repository while resolving or comparing instructions.
2. **Offline.** Resolution, policy evaluation, snapshots, and Git-ref analysis require no vendor APIs or network access.
3. **No instruction execution.** Markdown is data; `agentwhich` never executes commands it finds.
4. **Unknown beats guessed.** Potential source impact stays potential unless target resolution proves it.
5. **Adapters stay independent.** Each agent resolver models its own documented behavior.
6. **CI must be deterministic.** Policy and snapshots ignore user-global instruction files.

## Scope

`agentwhich` is not an AI assistant, prompt manager, RAG layer, or agent framework. It is a small diagnostic and policy tool for one problem:
**instruction discovery and drift across coding agents.**

## Roadmap

- **v0.4:** snapshots, PR impact analysis, and monorepo scoping.
- **v0.5:** baseline-file comparison, richer CI annotations, and performance work for very large monorepos.
- **v1.0:** stable adapter contract and versioned vendor compatibility matrix.

## Development

```bash
ruff check .
pytest
agentwhich check --policy .agentwhich.toml
python -m build
```

MIT licensed.
