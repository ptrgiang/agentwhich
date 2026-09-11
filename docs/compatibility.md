# Vendor compatibility notes

Last verified: **2026-09-12**.

`agentwhich` intentionally models documented discovery behavior rather than executing the vendor CLIs. When a vendor does not document precedence or runtime state, the resolver keeps the result conservative.

## Codex

Modeled behavior:

- `AGENTS.override.md` before `AGENTS.md`.
- User-level files under `CODEX_HOME` / `~/.codex`.
- Repository-to-working-directory hierarchy.
- `project_doc_fallback_filenames` from `config.toml`.

## Claude Code

Primary reference:

- https://code.claude.com/docs/en/memory

Modeled behavior:

- Managed, user, project, local, and nested `CLAUDE.md` sources.
- `./.claude/CLAUDE.md` project instructions.
- Inline `@path` imports with a four-hop recursion limit and code-fence/code-span skipping.
- `.claude/rules/**/*.md` unconditional rules and `paths:` frontmatter.
- Descendant memory files activated by a supplied target path.

Known static-analysis limitation:

- Claude can require one-time approval for project imports that resolve outside the working directory. `agentwhich` can find the file but cannot know the user's prior approval decision without reading Claude's private runtime state, so it does not claim approval status.

## Gemini CLI

Primary reference:

- https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md

Modeled behavior:

- Global, workspace/ancestor, and just-in-time context files.
- Target-path JIT discovery.
- `@file` imports.
- `context.fileName` customization from `.gemini/settings.json`.

Known static-analysis limitation:

- Workspace trust and ignore behavior can affect runtime loading. The current resolver models file discovery and target hierarchy, not the full Gemini trust/ignore subsystem.

## GitHub Copilot CLI

Primary reference:

- https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions

Modeled behavior:

- `~/.copilot/copilot-instructions.md` and personal `instructions/**/*.instructions.md`.
- `.github/copilot-instructions.md`.
- `.github/instructions/**/*.instructions.md` with `applyTo`.
- `AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md`, and `GEMINI.md` discovery.
- `COPILOT_CUSTOM_INSTRUCTIONS_DIRS`.
- `@path` imports for the file types documented as supporting imports.
- Deduplication of identical active instruction content.

Known static-analysis limitation:

- Copilot CLI lets users disable individual instruction files with `/instructions`. That interactive session state is not inferred by `agentwhich`.
