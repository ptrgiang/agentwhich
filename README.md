# agentwhich

> **`which` + `diff` for AI coding instructions.**

Why does Claude follow one repository rule while Codex ignores it?

`agentwhich` is a tiny, read-only CLI that predicts which repository instruction files an AI coding agent will load for a working directory, explains **why** each file applies, and compares the effective source set across agents.

**No LLM. No API key. No network. No telemetry.**

## The 20-second demo

```bash
pip install -e .
agentwhich compare --cwd . --agents codex,claude,gemini
```

Example:

```text
CODEX
-----
   1 ./AGENTS.md

CLAUDE
------
   1 ./CLAUDE.md

GEMINI
------
   1 ./GEMINI.md

DIFF
----
  codex-only:
    ./AGENTS.md
  claude-only:
    ./CLAUDE.md
  gemini-only:
    ./GEMINI.md
  shared by all: 0
  status: divergent
```

Same repo. Same directory. Different AI context.

## Why this exists

AI coding tools do not discover project instructions the same way. Codex has `AGENTS.md` and `AGENTS.override.md` resolution, Claude Code has `CLAUDE.md`, local files, imports and rules, while Gemini CLI has hierarchical `GEMINI.md` context and imports.

Humans see a folder tree. Agents see **different effective context graphs**.

`agentwhich` makes that invisible configuration visible before you start an agent session.

## Install

From source today:

```bash
git clone https://github.com/ptrgiang/agentwhich.git
cd agentwhich
python -m pip install -e .
```

For contributors:

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
```

## Commands

Explain one agent:

```bash
agentwhich explain --agent codex --cwd services/payments
agentwhich explain --agent claude --cwd services/payments
agentwhich explain --agent gemini --cwd services/payments
```

Compare agents:

```bash
agentwhich compare \
  --cwd services/payments \
  --agents codex,claude,gemini
```

JSON for scripts or CI:

```bash
agentwhich compare --cwd . --agents codex,claude --format json
```

If `.git` is not available or you want deterministic fixture behavior, provide the root explicitly:

```bash
agentwhich compare --repo ./examples/mixed-repo --cwd ./examples/mixed-repo/services/payments
```

## v0.1 support

| Agent | Startup hierarchy | Imports | Overrides | Lazy candidates |
|---|---:|---:|---:|---:|
| Codex | ✅ | n/a | ✅ | n/a |
| Claude Code | ✅ | ✅ | n/a | ✅ conservative |
| Gemini CLI | ✅ | ✅ | n/a | ✅ conservative |
| GitHub Copilot CLI | planned | planned | planned | planned |

The runtime agent is always the final authority. `agentwhich` intentionally says **unknown/candidate** instead of inventing behavior where vendor semantics are dynamic or underspecified.

## What it does not do

- does not call an LLM
- does not rewrite your instruction files
- does not execute commands found inside Markdown
- does not judge whether your instructions are “good”
- does not upload repository context
- does not promise that a model will obey an instruction

That narrow scope is the feature.

## Privacy and security

By default, instruction bodies are never printed. `agentwhich` reports local paths, resolution reasons, sizes, line counts and SHA-256 hashes. Imports are read as data only; nothing discovered in Markdown is executed.

## Roadmap

- **v0.1** — Codex, Claude Code and Gemini CLI; `explain`, `compare`, JSON output
- **v0.2** — target-file simulation and path-scoped rules; GitHub Copilot CLI adapter
- **v0.3** — `agentwhich check`, GitHub Action/SARIF, compatibility policy mode
- **v1.0** — stable adapter contract and published compatibility matrix

## Design rules

1. **Read-only core.** Never edit an instruction file.
2. **Offline core.** No model/API/telemetry dependency.
3. **Unknown beats guessed.** Dynamic or undocumented behavior is labeled honestly.
4. **Adapters stay independent.** Similar-looking vendors are not assumed to behave the same.

## Contributing

Resolver changes should include a regression fixture and link to authoritative vendor behavior when possible. Real-world weird monorepo layouts are especially welcome as issues.

## License

MIT.
