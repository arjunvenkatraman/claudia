# Coding-Agent / Model commit tags

Every commit in a repo with this hook gets standard git trailers naming the
coding agent that produced it, and the model it was running:

```
feat: add guided setup wizard (#6)

containerconf/setup.sh now prompts per machine.

Coding-Agent: opencode
Model: claude-sonnet-4-6
```

## Why

You often can't tell from a commit whether a human or an agent wrote it,
which agent, or which model. `Coding-Agent:` and `Model:` trailers record
both in the git history itself — visible in `git log`, GitHub, and any
tooling that parses trailers — with no extra infrastructure.

## How detection works

The `prepare-commit-msg` hook inspects the environment at commit time for the
agent:

| Environment | Result |
|---|---|
| `CLAUDECODE=1` and `CLAUDE_CODE_ENTRYPOINT` set | `Coding-Agent: claude` |
| `OPENCODE=1` set | `Coding-Agent: opencode` |
| neither (e.g. `git commit` from a plain terminal) | `Coding-Agent: manual` |

A commit never goes untagged, and an agent never claims a human commit: the
default is `manual`, so human commits are labeled by omission of agent markers,
not by an agent's assumption.

For `Model:`, the hook shells out to `claudia --current-model`, which reads
the actual model from the invoking agent's own session log rather than an env
var (neither agent reliably exports the running model into its env — see
[ADR-007](decisions/ADR-007-agent-model-trailer.md)):

| Agent | Model source | Fallback |
|---|---|---|
| `claude` | Claude Code's own JSONL transcript for `CLAUDE_CODE_SESSION_ID` | `unknown` if session file/model not found |
| `opencode` | `opencode.db`'s most recently updated session in this directory | `unknown` if db missing/empty |
| `manual` | — | `n/a` (no agent, no model) |

If `claudia` isn't installed or the lookup errors, `Model:` is `unknown`
rather than blocking the commit.

## Install

Per repository, one of:

```bash
claudia --install-git-hook                        # current directory
claudia --install-git-hook /path/to/repo          # specific repo

python3 skills/project-scaffold/scaffold.py /path/to/repo --install-git-hook   # existing project
python3 skills/project-scaffold/scaffold.py /path/to/new-project --name x --summary y  # auto-installs
```

Installing writes an executable `.git/hooks/prepare-commit-msg`. If the repo
uses `core.hooksPath`, the hook is written there instead. Re-running is
idempotent (it overwrites with the canonical copy, so the installed hook always
matches this repo's version).

Verify it works:

```bash
git commit --amend --no-edit --dry-run >/dev/null 2>&1
# simpler: make any commit, then
git log -1 --format="%(trailers)"
```

Expected for a terminal commit: `Coding-Agent: manual` and `Model: n/a`.

## Behavior details

- **Amend / merge / rebase** — the trailer is kept at exactly one per commit;
  re-running the hook on an amend does not duplicate it.
- **Merges made on GitHub** — the merge commit is authored outside the repo's
  hook (GitHub's UI), so it carries no trailer. That is expected and fine: the
  source commits are tagged.
- **The default is manual** — set the agent env vars yourself (e.g. inside a
  container) and *you* get tagged `opencode`/`claude`, which is why the hook
  keys off the agent's own markers, not the shell.

## Inspecting

```bash
git log --format="%h %s%n    %(trailers:key=Coding-Agent)%n    %(trailers:key=Model)"
git log -1 --pretty=%B                       # see the full message + trailers
```

## In this repo

- Canonical hook source: `skills/project-scaffold/prepare-commit-msg.sh`.
- `claudia --install-git-hook` embeds a byte-identical copy; a drift-guard test
  fails if the two ever diverge.
- Design notes: [ADR-005](../docs/decisions/ADR-005-agent-git-trailers.md)
  (agent trailer) and [ADR-007](decisions/ADR-007-agent-model-trailer.md)
  (model trailer).
- **Existing repos with the hook already installed**: `--install-git-hook`
  skips if `.git/hooks/prepare-commit-msg` already exists, so upgrading to
  get `Model:` on a repo tagged before ADR-007 means removing the old hook
  file first, then reinstalling.
