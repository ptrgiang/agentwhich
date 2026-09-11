# Git snapshots and PR impact

`agentwhich` v0.4 adds two read-only primitives for reviewing instruction context over time:

- `snapshot`: capture repository-local effective context for a working tree or Git ref.
- `changed`: compare the merge base of two refs with the head ref and explain which changed paths see different instruction context.

## Snapshot

```bash
agentwhich snapshot --target src/api/handler.ts
```

The JSON snapshot records only active instruction layers inside the repository. Each layer includes:

- repository-relative path;
- activation phase;
- SHA-256 content digest;
- resolver order.

User-global configuration is isolated while snapshotting so two CI runners do not produce different repository snapshots because one happens to have `~/.codex`, `~/.claude`, `~/.gemini`, or Copilot custom instruction directories.

Use `--ref` for a committed historical state:

```bash
agentwhich snapshot --ref main --target src/api/handler.ts
```

The ref is materialized from `git archive` into a temporary directory. The source repository is never checked out, reset, or modified.

## PR impact

```bash
agentwhich changed --base origin/main --head HEAD
```

`changed` resolves both refs to commits, computes their merge base, and uses that merge base as the comparison baseline. This matches the question a pull-request reviewer normally cares about: **what did this branch change relative to where it forked?**

For every changed path in scope, `agentwhich` resolves the selected agents against both historical trees and compares active repository-local context.

Confirmed target impact includes:

- an instruction layer becoming active;
- an instruction layer no longer being active;
- active instruction content changing at the same path;
- an activation phase changing;
- active instruction order changing.

## Potential broader impact

A path-scoped rule can change without any matching source file changing in the same PR. In that case `agentwhich` cannot prove all files that would be affected without scanning the repository and guessing future work.

Known instruction-source changes are therefore surfaced separately as `potential broader impact`. They do not make `--fail-on-impact` fail unless a changed target also proves a context difference.

This preserves the project rule: **unknown beats guessed**.

## Monorepos

Use `--cwd` as a package/workspace boundary:

```bash
agentwhich changed \
  --cwd packages/payments \
  --base origin/main \
  --head HEAD
```

Only changed paths inside that subtree are evaluated, and agent startup hierarchy is resolved from that working directory. This is especially important for agents such as Codex whose startup instruction discovery depends on the working directory hierarchy.

A CI matrix can run one command per workspace rather than scanning the whole monorepo every time.

## Limits

`changed` evaluates at most 200 changed paths by default. Use a narrower `--cwd` or explicitly disable the cap:

```bash
agentwhich changed --base origin/main --max-targets 0
```

The cap protects CI from unexpectedly expensive analysis on generated or bulk-change branches.

## Git requirements and safety

Git is required for `changed` and `snapshot --ref`; other commands keep working without invoking the Git executable.

Ref-aware commands:

- pass Git arguments without a shell;
- resolve refs to commit SHAs before diff/archive operations;
- reject ref strings beginning with `-`;
- materialize only regular files and directories from Git archives;
- skip archive symlinks, hard links, and submodule contents rather than following them outside the temporary tree.

Because historical symlink targets and submodule contents are not materialized, instruction files provided only through those mechanisms are intentionally not modeled in ref snapshots yet.
