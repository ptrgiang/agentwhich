# Changelog

All notable changes to `agentwhich` are documented here.

## 0.2.0 - 2026-09-12

### Added

- GitHub Copilot CLI adapter.
- Target-aware Claude `.claude/rules/**/*.md` evaluation from `paths:` frontmatter.
- Target-aware Claude descendant `CLAUDE.md` and `CLAUDE.local.md` discovery.
- Gemini just-in-time target-path context discovery.
- Gemini `context.fileName` support from `.gemini/settings.json`.
- Copilot `applyTo` matching for `*.instructions.md` files.
- Copilot custom instruction directories via `COPILOT_CUSTOM_INSTRUCTIONS_DIRS`.
- First-class `target` phase in JSON and text output.

### Changed

- Claude imports now recognize inline `@path` references, ignore fenced code/code spans, and use the documented four-hop limit.
- Comparison treats target-activated files as active instruction sources.
- Relative `--target` paths resolve from `--cwd` rather than the shell process directory.

## 0.1.0 - 2026-09-11

- Initial working alpha with Codex, Claude Code, and Gemini CLI resolvers.
- `explain` and `compare` commands with text and JSON output.
- Offline, read-only, dependency-free runtime.
