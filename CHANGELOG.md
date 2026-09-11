# Changelog

All notable changes to `agentwhich` are documented here.

## 0.4.0 - 2026-09-12

### Added

- `agentwhich snapshot` for deterministic repository-local context snapshots.
- Historical snapshots from a Git ref without checking out or mutating the repository.
- `agentwhich changed` for pull-request instruction impact analysis.
- Merge-base comparison semantics for `--base` and `--head`.
- Per-target added, removed, content-changed, phase-changed, and reordered instruction reporting.
- Conservative `potential broader impact` reporting for changed instruction sources whose full scope cannot be proven.
- `--fail-on-impact` for opt-in CI gating on confirmed context changes.
- `--cwd` subtree scoping and a configurable `--max-targets` guard for monorepos.
- Git impact and snapshot documentation in `docs/impact.md`.

### Changed

- Version bumped to 0.4.0.
- CI now fetches full Git history and dogfoods `agentwhich changed` on pull requests.
- README now documents snapshot, PR impact, and monorepo workflows.
- Ref-aware snapshots isolate user-global agent configuration for deterministic output.

## 0.3.0 - 2026-09-12

### Added

- `agentwhich check` with exit codes designed for CI (`0` pass, `1` violation, `2` configuration error).
- `.agentwhich.toml` policy files.
- Per-agent `require`, `forbid`, and `max_active` assertions.
- Optional `require_instructions`, `fail_on_warnings`, `fail_on_divergence`, and `require_target` gates.
- JSON and SARIF 2.1.0 check output.
- Stable policy rule IDs `AW001` through `AW007`.
- Composite GitHub Action with optional Code Scanning SARIF upload.
- Policy reference documentation in `docs/policy.md`.

### Changed

- Policy evaluation only considers active instruction files inside the repository so CI is not affected by user-global agent configuration.
- README now includes policy, SARIF, and GitHub Action quick starts.

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
