#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# --- Ephemeral track ------------------------------------------------------
# A throwaway container (--rm, no name) with an OPTIONAL synced folder bound
# at /xpal-data-remote. A fresh container every launch, so it always uses the
# latest built image and can take a different remote each time.
#
#   No remote:                  ./run-ephemeral.sh
#   Mount a remote (per run):   ./run-ephemeral.sh "/path/to/ProjectA"
#   Or via env var:             XPAL_REMOTE="/path/to/ProjectB" ./run-ephemeral.sh
#
# Prerequisite: the folder must already exist on this filesystem (e.g. a
# SharePoint library synced locally by the OneDrive/SharePoint sync client).
# On macOS that's usually under ~/Library/CloudStorage/OneDrive-<org>/...

IMAGE="$XPAL_IMAGE"

# Optional remote path: first CLI arg wins, else $XPAL_REMOTE, else the value
# captured by setup.sh (containerconf/.env).
REMOTE_DIR="${1:-${XPAL_REMOTE:-${XPAL_HOST_REMOTE_DIR:-}}}"

# Base mounts — always present (same paths as the day-to-day track).
MOUNTS=(
  -v "$XPAL_HOST_SRC":/xpal-src:Z
  -v "$XPAL_HOST_DATA":/xpal-data:Z
  -v "$XPAL_HOST_AUTH":/xpal-auth:Z
)

# Conditionally add the remote mount only when a path was supplied.
if [ -n "$REMOTE_DIR" ]; then
  if [ ! -d "$REMOTE_DIR" ]; then
    echo "Error: remote folder does not exist: $REMOTE_DIR" >&2
    echo "(Is the library synced and available offline?)" >&2
    exit 1
  fi
  MOUNTS+=( -v "$REMOTE_DIR":/xpal-data-remote:Z )
  echo "Remote: $REMOTE_DIR -> /xpal-data-remote"
else
  echo "No remote folder mounted."
fi

exec "$XPAL_RUNTIME" run -it --rm \
  --userns=keep-id \
  "${PORT_ARGS[@]}" \
  "${MOUNTS[@]}" \
  "$IMAGE"
