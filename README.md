# agentwhich

`which` + `diff` for AI coding-agent instructions.

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

## v0.2 highlights

- Target-aware Claude `.claude/rules/**/*.md` evaluation via `paths:` frontmatter.
- Target-aware Claude descendant `CLAUDE.md` / `CLAUDE.local.md` loading.
- Claude inline `@path` imports, fenced/code-span skipping, and the documented four-hop limit.
- Gemini JIT target-path context plus `context.fileName` from `.gemini/settings.json`.
- GitHub Copilot CLI adapter covering personal, repository, agent, modular, and custom-directory instructions.
- Copilot `applyTo` matching, supported `@path` imports, and identical-content deduplication.
- `target` is now a first-class active phase in explain/compare output.

## Design rules

1. **Read-only.** Never mutate the repository while resolving instructions.
2. **Offline.** Resolution must not require vendor APIs or network access.
3. **No instruction execution.** Markdown is data; `agentwhich` never executes commands it finds.
4. **Unknown beats guessed.** When vendor behavior is ambiguous, surface a candidate/warning instead of inventing precedence.
5. **Adapters stay independent.** Each agent resolver models its own documented behavior.

## Scope

`agentwhich` is not an AI assistant, prompt manager, RAG layer, or agent framework. It is a small diagnostic tool for one problem:
**instruction discovery and drift across coding agents.**

## Roadmap

- **v0.3:** `agentwhich check`, CI policy assertions, GitHub Action/SARIF output.
- **v1.0:** stable adapter contract and versioned vendor compatibility matrix.

## Development

```bash
ruff check .
pytest
python -m build
```

MIT licensed.
