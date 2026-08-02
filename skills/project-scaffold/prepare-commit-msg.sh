#!/usr/bin/env bash
# prepare-commit-msg — append a `Coding-Agent:` trailer naming the coding agent
# that produced this commit. Detection is via the env markers that Claude Code
# and OpenCode set in every shell they spawn:
#
#   Claude Code — CLAUDECODE=1, CLAUDE_CODE_ENTRYPOINT=cli
#   OpenCode    — OPENCODE=1, OPENCODE_PID=<pid>
#
# When no marker is present the commit is labeled `manual` (a human/terminal
# commit) — an agent never silently claims a manual commit.
#
# Idempotent: if the message already carries a Coding-Agent trailer it is left
# untouched, so `--amend`, merge, and squash commits are safe.
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

# Rebuild the message with the trailer appended after a blank line (git-trailer
# style), stripping stray trailing blank lines/whitespace first.
body="$(cat "$MSG_FILE")"
body="$(printf '%s' "$body" | sed -e 's/[[:space:]]*$//')"

if [ -n "$body" ]; then
  printf '%s\n\nCoding-Agent: %s\n' "$body" "$AGENT" > "$MSG_FILE"
else
  printf 'Coding-Agent: %s\n' "$AGENT" > "$MSG_FILE"
fi

exit 0
