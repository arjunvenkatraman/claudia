#!/usr/bin/env bash
# Pre-publication leak scanner.
#
# Scans TRACKED files for strings that could identify the original author or
# their machine: real names/usernames, secret tokens, host-specific paths,
# localhost ports, and tracked local state (.DS_Store, .claude/, .env).
#
# Tiering:
#   CRITICAL — always fails (secrets, identity, host state). Fix before any push.
#   REVIEW   — printed but does not fail unless --strict (internal naming that
#              is fine for a private repo but should be renamed for a public one).
#
# Usage (from the repo root):
#   ./scripts/scrub-public.sh          # scan
#   ./scripts/scrub-public.sh --strict # treat REVIEW items as failures too
#   ./scripts/scrub-public.sh --quiet  # only print problems

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

STRICT=0
QUIET=0
for arg in "$@"; do
  case "$arg" in
    --strict) STRICT=1 ;;
    --quiet)  QUIET=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

# Files that intentionally reference the scanned tokens: this script, its doc,
# and docs that legitimately cite the repo's own issue URL and documented
# localhost port. Exempting them is the same tradeoff the script already makes
# for its own files — keep the list narrow.
EXEMPT="^(scripts/scrub-public\.sh|docs/public-release\.md|docs/filing-issues\.md|docs/usage\.md)$"

# Tracked files, excluding the intentionally-exempt files.
mapfile -t FILES < <(git ls-files | grep -vE "$EXEMPT")
if [ "${#FILES[@]}" -eq 0 ]; then
  echo "No tracked files to scan."
  exit 0
fi

CRITICAL_OPTS=(-n -i -E)
REVIEW_OPTS=(-n -E)

CRITICAL_PATTERNS=(
  "ananda"                                   # username
  "arjun"                                    # given name
  "venkatraman"                              # family name
  "localhost:[0-9]+"
  "sk-ant-api[0-9a-zA-Z_-]{10,}"
  "sk-ant-admin[0-9a-zA-Z_-]{10,}"
  "ghp_[0-9A-Za-z]{30,}"
  "glpat-[0-9A-Za-z_-]{20,}"
  "AKIA[0-9A-Z]{16}"
  "-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"
  "OneDrive-[A-Za-z0-9]"
  "/Users/[A-Za-z]"
)

REVIEW_PATTERNS=(
  "xpal"                                     # internal project prefix
  "swarashruti"                              # internal workspace project name
  "eka-bodhi"                                # internal workspace project name
)

CRITICAL_HITS=0
REVIEW_HITS=0

echo "Scanning ${#FILES[@]} tracked files for potential leaks..."
echo

for pat in "${CRITICAL_PATTERNS[@]}"; do
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    [ "$QUIET" = "1" ] || echo "  CRITICAL: $line"
    CRITICAL_HITS=$((CRITICAL_HITS + 1))
  done < <(grep "${CRITICAL_OPTS[@]}" "$pat" "${FILES[@]}" 2>/dev/null)
done

for pat in "${REVIEW_PATTERNS[@]}"; do
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    [ "$QUIET" = "1" ] || echo "  REVIEW:   $line"
    REVIEW_HITS=$((REVIEW_HITS + 1))
  done < <(grep "${REVIEW_OPTS[@]}" "$pat" "${FILES[@]}" 2>/dev/null)
done

# Tracked local-state checks (fail outright). .env.example is documentation
# and is intentionally committed; everything else under that name is not.
if git ls-files | grep -vE "^containerconf/\.env\.example$" | grep -qE "(^|/)(\.DS_Store|\.env|\.env\..*)$"; then
  [ "$QUIET" = "1" ] || echo "  CRITICAL: tracked local/state file (.DS_Store or .env) — untrack it and gitignore."
  CRITICAL_HITS=$((CRITICAL_HITS + 1))
fi
if git ls-files | grep -q "^\.claude/"; then
  [ "$QUIET" = "1" ] || echo "  CRITICAL: tracked machine settings under .claude/ — untrack and gitignore."
  CRITICAL_HITS=$((CRITICAL_HITS + 1))
fi

echo
if [ "$CRITICAL_HITS" -gt 0 ]; then
  echo "FAIL: $CRITICAL_HITS critical hit(s). See docs/public-release.md for how to fix."
  exit 1
fi
if [ "$REVIEW_HITS" -gt 0 ] && [ "$STRICT" = "1" ]; then
  echo "FAIL (--strict): $REVIEW_HITS review item(s). Rename internal naming before a public push."
  exit 1
fi
echo "OK: no critical leaks. ${REVIEW_HITS} review item(s)${STRICT:+ (allowed)}."
exit 0
