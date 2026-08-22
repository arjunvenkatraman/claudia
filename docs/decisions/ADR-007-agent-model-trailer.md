# ADR-007: `Model:` git trailer alongside `Coding-Agent:`

**Status:** Accepted

## Context

ADR-005 gives every commit a `Coding-Agent:` trailer (`claude` | `opencode` |
`manual`), but not which *model* produced it. Both agents can run several
models across a work session (e.g. Sonnet vs. Haiku, or a user override), so
"which agent" alone doesn't answer "which model wrote this diff" for
attribution, cost analysis, or auditing.

Unlike agent identity, model identity has no standard env marker that's
reliably set for the actual running model:

- Claude Code accepts `ANTHROPIC_MODEL` (alias `CLAUDE_MODEL`) as an
  *override* input, but doesn't export the effective model back into the
  environment of shells it spawns — in a default session (no override) the
  variable is simply unset, even though the CLI is definitely running some
  specific model.
- OpenCode has no documented per-shell model env var either.

So the hook can't do for `Model:` what it does for `Coding-Agent:` (read an
env var and be done). It needs a real per-invocation lookup.

Both agents do, however, persist the actual model used in their own session
logs, and claudia already parses both formats for `claudia index` (ADR-006):

- **Claude Code** — JSONL transcripts under `claude_dir()/projects/**/`,
  filename == session id, each assistant message carries `message.model`.
  `CLAUDE_CODE_SESSION_ID` is set in every shell Claude Code spawns, so the
  exact transcript file is a direct glob, not a scan of history.
- **OpenCode** — `opencode.db`'s `session` table has a `model` column
  (sometimes a plain string, sometimes a JSON blob `{"id", "providerID"}`).
  OpenCode sets no per-shell session-id marker, so there's no exact-match
  lookup available; the most recently updated session in the current working
  directory is used as a stand-in for "current".

A hook must stay fast (it runs on every commit) and must not fail the commit
if the lookup can't complete. `claudia index`'s reporting-tools path
(`opencode export` per session) is both too slow (subprocess per session) and
overkill (full accounting, not just a model id) for this.

## Decision

Add `claudia --current-model`, a fast, single-purpose lookup deliberately
separate from `claudia index`:

- **Claude**: `_current_claude_model()` globs
  `claude_dir()/projects/**/<CLAUDE_CODE_SESSION_ID>.jsonl` (O(1), no
  directory walk over unrelated sessions) and returns the last non-synthetic
  `message.model` seen. `unknown` if the session id or file is missing.
- **OpenCode**: `_current_opencode_model()` reads `opencode.db` directly
  (no `opencode` CLI subprocess) — `SELECT model FROM session ... AND
  directory = ? ORDER BY time_updated DESC LIMIT 1`, falling back to the
  most-recently-updated session overall if no directory match. `unknown` if
  the db is missing or empty.
- **Manual**: `n/a` — there is no agent, so no model to attribute.

The `prepare-commit-msg` hook (both the canonical
`skills/project-scaffold/prepare-commit-msg.sh` and the embedded copy in
`claudia.py`) keeps its existing bash-only `Coding-Agent:` detection (env
markers, no subprocess) and, only when the agent isn't `manual`, shells out to
`claudia --current-model` for `Model:`. If `claudia` isn't on `PATH` or the
call fails, `Model:` falls back to `unknown` — the commit is never blocked on
this lookup.

Both trailers are appended together in the same idempotency check: if
`Coding-Agent:` is already present (amend/merge/squash), neither trailer is
touched.

### `claude_dir()` fix required for this to work in this project's own container

`claude_dir()` previously only checked `CLAUDIA_CLAUDE_DIR` (an explicit,
claudia-specific override), defaulting straight to `~/.claude`. This
project's own container setup (`docs/container-env.md`) relocates Claude
Code's data to `$CLAUDE_CONFIG_DIR` (`/xpal-auth/claude`) without setting
`CLAUDIA_CLAUDE_DIR` — so `claude_dir()` was silently reading an empty
directory in that setup, and every claudia command (not just this one) was
reporting "No matching usage data found." `claude_dir()` now falls back to
`CLAUDE_CONFIG_DIR` before defaulting to `~/.claude`. Tests that isolate
`claude_dir()` via `_with_home()` now also clear both env vars, since
otherwise a real `CLAUDE_CONFIG_DIR` in the test-running environment leaks
real session data into fixture-based assertions.

## Consequences

- **Best-effort, not guaranteed.** `Model:` is `unknown` whenever the
  targeted lookup can't resolve a model (rare: missing session file,
  archived/cleared opencode db, `claudia` not installed). It is never wrong
  by omission the way `Coding-Agent:` is designed to be — there's no
  `manual`-style safe default for "model", so `unknown` is the honest answer
  rather than a guess.
- **OpenCode's "current" is approximate.** Without a per-shell session id
  marker, the directory-scoped most-recent-session heuristic can misattribute
  the model if a developer runs two concurrent OpenCode sessions against the
  same repo. Accepted as adequate for the attribution/cost-analysis use case;
  revisit if OpenCode ships a session-id env marker.
- **One more subprocess per non-manual commit** (`claudia --current-model`).
  Kept fast deliberately (no `opencode export`, targeted glob instead of full
  JSONL scan) to stay hook-appropriate; still slower than the pure-bash
  `Coding-Agent:` detection it sits alongside.
- **`claude_dir()`'s new default changes behavior for anyone with
  `CLAUDE_CONFIG_DIR` set** but no `CLAUDIA_CLAUDE_DIR` override — from
  "silently read nothing" to "read Claude Code's actual relocated data",
  which is strictly a fix, but is a behavior change worth knowing about if
  something depended on the old (broken) empty-default behavior.
