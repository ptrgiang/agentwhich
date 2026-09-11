# agentwhich

`which` + `diff` + `check` for AI coding-agent instructions.

`agentwhich` answers a deceptively hard question: **what instruction files will this coding agent actually see here?**
It works offline and read-only: no LLM, no API key, no network, no telemetry, and no runtime dependencies.

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

## Enforce a policy

v0.3 adds `agentwhich check`: turn instruction discovery into a CI gate.

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

Exit codes are intentionally CI-friendly:

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

The repository is also a composite GitHub Action. It can generate SARIF, optionally upload it, and fail the job after policy violations are reported.

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
      - uses: ptrgiang/agentwhich@v0.3.0
        with:
          policy: .agentwhich.toml
          upload-sarif: 'true'
```

Set `upload-sarif: 'false'` when you only want the policy gate or when Code Scanning upload is unavailable.

## v0.3 highlights

- `agentwhich check` with deterministic policy assertions.
- `.agentwhich.toml` with per-agent `require`, `forbid`, and `max_active` rules.
- Optional gates for missing instructions, warnings, divergence, and required targets.
- Text, JSON, and SARIF output.
- Composite GitHub Action with optional Code Scanning upload.
- Stable rule IDs (`AW001`–`AW007`) for CI integrations.

## Design rules

1. **Read-only.** Never mutate the repository while resolving instructions.
2. **Offline.** Resolution and policy evaluation must not require vendor APIs or network access.
3. **No instruction execution.** Markdown is data; `agentwhich` never executes commands it finds.
4. **Unknown beats guessed.** When vendor behavior is ambiguous, surface a candidate/warning instead of inventing precedence.
5. **Adapters stay independent.** Each agent resolver models its own documented behavior.
6. **CI must be deterministic.** Policy rules ignore user-global instruction files.

## Scope

`agentwhich` is not an AI assistant, prompt manager, RAG layer, or agent framework. It is a small diagnostic and policy tool for one problem:
**instruction discovery and drift across coding agents.**

## Roadmap

- **v0.3:** policy checks, SARIF, and GitHub Action.
- **v0.4:** baseline snapshots and changed-file / monorepo policy workflows.
- **v1.0:** stable adapter contract and versioned vendor compatibility matrix.

## Development

```bash
ruff check .
pytest
agentwhich check --policy .agentwhich.toml
python -m build
```

MIT licensed.
