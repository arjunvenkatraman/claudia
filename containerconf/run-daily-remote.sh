#!/usr/bin/env bash
set -e

# --- Day-to-day + remote track ---------------------------------------------
# A long-lived, named container like run-daily.sh, but also binds an OPTIONAL
# SharePoint folder at /xpal-data-remote. Separate from 'xpal-dev' because
# mounts are fixed at container creation — a container with a remote mount
# can't be the same container as one without.
#
#   First run (creates it):     ./run-daily-remote.sh "/path/to/SharePoint/ProjectA"
#                                or: XPAL_REMOTE="/path/to/ProjectA" ./run-daily-remote.sh
#   Re-enter later:              podman start -ai xpal-dev-remote
#   Extra shell into it:        podman exec -it xpal-dev-remote zsh
#   Refresh after a rebuild:    rm it manually, then re-run this script
#     (build.sh only offers to refresh 'xpal-dev', not this variant)
#
# NOTE: the remote path is only bound at CREATION time, same as the other
# mounts. Once 'xpal-dev-remote' exists, re-running this script just starts
# and attaches to it — passing a different path/env var has no effect until
# you remove and recreate the container.
#
# Prerequisite: the SharePoint library must be SYNCED to a local folder (via
# the OneDrive/SharePoint sync client) so the path exists on this filesystem.

IMAGE="xpal-claudia"
CONTAINER="xpal-dev-remote"

# If it already exists, don't create a second one — restart and attach instead.
if podman container exists "$CONTAINER"; then
  echo "Container '$CONTAINER' already exists — starting and attaching."
  echo "(Remote mount, if any, was fixed at creation — see script header.)"
  exec podman start -ai "$CONTAINER"
fi

# Optional remote path: first CLI arg wins, else $XPAL_REMOTE, else none.
REMOTE_DIR="${1:-${XPAL_REMOTE:-}}"

MOUNTS=(
  -v "$HOME/Development/xpal-src":/xpal-src:Z
  -v "$HOME/Development/xpal-data":/xpal-data:Z
  -v "$HOME/Development/xpal-auth":/xpal-auth:Z
)

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

echo "Creating day-to-day+remote container '$CONTAINER'..."
exec podman run -it --name "$CONTAINER" \
  --userns=keep-id \
  -p 5001:5001 \
  -p 8001:8001 \
  -p 8080:8080 \
  "${MOUNTS[@]}" \
  "$IMAGE"
