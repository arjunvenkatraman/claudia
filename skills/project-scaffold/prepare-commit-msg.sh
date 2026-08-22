#!/usr/bin/env bash
# prepare-commit-msg — append `Coding-Agent:` and `Model:` trailers recording
# the coding agent and model that produced this commit. Agent detection is via
# the env markers that Claude Code and OpenCode set in every shell they spawn:
#
#   Claude Code — CLAUDECODE=1, CLAUDE_CODE_ENTRYPOINT=cli
#   OpenCode    — OPENCODE=1, OPENCODE_PID=<pid>
#
# When no marker is present the commit is labeled `manual` (a human/terminal
# commit) — an agent never silently claims a manual commit, and `Model:` is
# `n/a` since there is no agent to attribute a model to.
#
# Model lookup shells out to `claudia --current-model`, which does a fast,
# targeted read of the invoking session's own log (Claude Code JSONL keyed by
# CLAUDE_CODE_SESSION_ID, or OpenCode's session database) — see
# docs/decisions/ADR-007-agent-model-trailer.md. If `claudia` isn't on PATH or
# the lookup fails, Model falls back to `unknown` rather than blocking the
# commit.
#
# Idempotent: if the message already carries a Coding-Agent trailer both
# trailers are left untouched, so `--amend`, merge, and squash commits are
# safe.
#
# Install via the project-scaffold skill (`scaffold.py init` or
# `scaffold.py <dir> --install-git-hook`) or `claudia --install-git-hook`.

set -u
MSG_FILE="${1:-}"

if [ -z "$MSG_FILE" ] || [ ! -f "$MSG_FILE" ]; then
  exit 0
fi

# Already tagged — do nothing.
if grep -qiE '^Coding-Agent:' "$MSG_FILE"; then
  exit 0
fi

AGENT="manual"
if [ "${CLAUDE_CODE_ENTRYPOINT:-}" != "" ] || [ "${CLAUDECODE:-}" = "1" ]; then
  AGENT="claude"
elif [ "${OPENCODE:-}" = "1" ]; then
  AGENT="opencode"
fi

MODEL="n/a"
if [ "$AGENT" != "manual" ]; then
  MODEL=""
  if command -v claudia >/dev/null 2>&1; then
    MODEL="$(claudia --current-model 2>/dev/null)"
  fi
  [ -z "$MODEL" ] && MODEL="unknown"
fi

# Rebuild the message with the trailers appended after a blank line (git-trailer
# style), stripping stray trailing blank lines/whitespace first.
body="$(cat "$MSG_FILE")"
body="$(printf '%s' "$body" | sed -e 's/[[:space:]]*$//')"

if [ -n "$body" ]; then
  printf '%s\n\nCoding-Agent: %s\nModel: %s\n' "$body" "$AGENT" "$MODEL" > "$MSG_FILE"
else
  printf 'Coding-Agent: %s\nModel: %s\n' "$AGENT" "$MODEL" > "$MSG_FILE"
fi

exit 0
