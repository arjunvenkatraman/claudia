#!/usr/bin/env bash
set -e

# --- Ephemeral track ------------------------------------------------------
# A throwaway container (--rm, no name) with an OPTIONAL SharePoint folder
# bound at /xpal-data-remote. A fresh container every launch, so it always
# uses the latest built image and can take a different remote each time.
#
#   No remote:                  ./run-ephemeral.sh
#   Mount a remote (per run):   ./run-ephemeral.sh "/path/to/SharePoint/ProjectA"
#   Or via env var:             XPAL_REMOTE="/path/to/ProjectB" ./run-ephemeral.sh
#
# Prerequisite: the SharePoint library must be SYNCED to a local folder (via
# the OneDrive/SharePoint sync client) so the path exists on this filesystem.
# On macOS that's usually under ~/Library/CloudStorage/OneDrive-<org>/...

IMAGE="xpal-claudia"

# Optional remote path: first CLI arg wins, else $XPAL_REMOTE, else none.
REMOTE_DIR="${1:-${XPAL_REMOTE:-}}"

# Base mounts — always present (same paths as the day-to-day track).
MOUNTS=(
  -v "$HOME/Development/xpal-src":/xpal-src:Z
  -v "$HOME/Development/xpal-data":/xpal-data:Z
  -v "$HOME/Development/xpal-auth":/xpal-auth:Z
)

# Conditionally add the remote mount only when a path was supplied.
if [ -n "$REMOTE_DIR" ]; then
  if [ ! -d "$REMOTE_DIR" ]; then
    echo "Error: remote folder does not exist: $REMOTE_DIR" >&2
    echo "(Is the SharePoint library synced and available offline?)" >&2
    exit 1
  fi
  MOUNTS+=( -v "$REMOTE_DIR":/xpal-data-remote:Z )
  echo "Remote: $REMOTE_DIR -> /xpal-data-remote"
else
  echo "No remote folder mounted."
fi

exec podman run -it --rm \
  --userns=keep-id \
  -p 5001:5001 \
  -p 8001:8001 \
  -p 8080:8080 \
  "${MOUNTS[@]}" \
  "$IMAGE"
