#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# --- Day-to-day + remote track ---------------------------------------------
# A long-lived, named container like run-daily.sh, but also binds an OPTIONAL
# synced folder at /xpal-data-remote. Separate from the plain day-to-day
# container because mounts are fixed at container creation — a container with
# a remote mount can't be the same container as one without.
#
#   First run (creates it):     ./run-daily-remote.sh "/path/to/ProjectA"
#                                or: XPAL_REMOTE="/path/to/ProjectA" ./run-daily-remote.sh
#   Re-enter later:              $XPAL_RUNTIME start -ai $XPAL_CONTAINER_REMOTE
#   Extra shell into it:        $XPAL_RUNTIME exec -it $XPAL_CONTAINER_REMOTE zsh
#   Refresh after a rebuild:    rm it manually, then re-run this script
#     (build.sh only offers to refresh the plain day-to-day container)
#
# NOTE: the remote path is only bound at CREATION time, same as the other
# mounts. Once the container exists, re-running this script just starts and
# attaches to it — passing a different path/env var has no effect until you
# remove and recreate the container.
#
# Prerequisite: the folder must already exist on this filesystem (e.g. a
# SharePoint library synced locally by the OneDrive/SharePoint sync client).

IMAGE="$XPAL_IMAGE"
CONTAINER="$XPAL_CONTAINER_REMOTE"

# If it already exists, don't create a second one — restart and attach instead.
if "$XPAL_RUNTIME" container exists "$CONTAINER"; then
  echo "Container '$CONTAINER' already exists — starting and attaching."
  echo "(Remote mount, if any, was fixed at creation — see script header.)"
  exec "$XPAL_RUNTIME" start -ai "$CONTAINER"
fi

# Optional remote path: first CLI arg wins, else $XPAL_REMOTE, else the value
# captured by setup.sh (containerconf/.env).
REMOTE_DIR="${1:-${XPAL_REMOTE:-${XPAL_HOST_REMOTE_DIR:-}}}"

MOUNTS=(
  -v "$XPAL_HOST_SRC":/xpal-src:Z
  -v "$XPAL_HOST_DATA":/xpal-data:Z
  -v "$XPAL_HOST_AUTH":/xpal-auth:Z
)

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

echo "Creating day-to-day+remote container '$CONTAINER'..."
exec "$XPAL_RUNTIME" run -it --name "$CONTAINER" \
  --userns=keep-id \
  "${PORT_ARGS[@]}" \
  "${MOUNTS[@]}" \
  "$IMAGE"
