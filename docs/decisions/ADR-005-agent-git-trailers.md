# ADR-005: Agent-attributed git commits via a `Coding-Agent` trailer

**Status:** Accepted

## Context

Work in this workspace is produced alternately by Claude Code and OpenCode, but
nothing records which agent created a given commit. For attribution, cost
analysis, and auditing (e.g. "which agent wrote this diff?") we want every
push/pull to carry that signal. Commits are the durable unit that flows through
push and pull, so the signal belongs on the commit.

Both agents set a marker in the environment of every shell they spawn, so any
git command they run can detect its parent agent with no code changes on the
agent side:

| Agent | Env marker |
|---|---|
| Claude Code | `CLAUDECODE=1`, `CLAUDE_CODE_ENTRYPOINT=cli` |
| OpenCode | `OPENCODE=1`, `OPENCODE_PID=<pid>` |

(Verified live: OpenCode sets `OPENCODE=1` in its Bash tool subprocesses.)

## Decision

Every commit gets a git trailer `Coding-Agent: <agent>` appended by a
`prepare-commit-msg` hook. `<agent>` is `claude`, `opencode`, or `manual`
(when no marker is present — a plain human/terminal commit).

**Hook behavior:**
- Runs only in `prepare-commit-msg`; if the message already has a
  `Coding-Agent:` trailer it is left untouched (idempotent, amend-safe).
- Appends the trailer separated by a blank line, standard git-trailer style,
  so GitHub and `git log --format=%B` render it cleanly.
- Detection order: Claude Code first, then OpenCode, else `manual`.

**Delivery (two paths, one canonical hook):**
1. The canonical hook lives with the `project-scaffold` skill as
   `skills/project-scaffold/prepare-commit-msg.sh`. `scaffold.py` installs it
   into `.git/hooks/prepare-commit-msg` (executable) on every `init`, and a
   new `--install-git-hook` action installs it into **existing** projects that
   predate this mechanism — so older scaffolds can pull the latest best
   practice without re-scaffolding.
2. `claudia --install-git-hook [PATH]` embeds the same hook (single-file CLI,
   works even when installed to `/usr/local/bin` away from the repo).

The scaffold's `CLAUDE.md` template documents the trailer in its Git workflow
section so new projects advertise the convention.

## Consequences

- **Attribution by default for new projects** and opt-in for old ones
  (`scaffold.py <dir> --install-git-hook`).
- **Clean git history**: trailers are standard and ignored by `git diff`;
  no changes to messages, only an appended trailer.
- **Works for manual commits too** — they are labeled `manual`, so an agent
  never silently claims a human commit.
- **Both agents must keep their env markers** — if a future agent stops
  setting them, commits fall back to `manual` (fail-safe, no false claims).
- **Merge/rebase commits** also get the trailer; acceptable and consistent.
