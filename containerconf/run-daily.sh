#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# --- Day-to-day track -----------------------------------------------------
# A long-lived, named container with stable mounts and NO remote folder.
# Create it once; re-enter it across sessions. Mounts are fixed at creation.
#
#   First run (creates it):     ./run-daily.sh
#   Re-enter later:             $XPAL_RUNTIME start -ai $XPAL_CONTAINER
#   Extra shell into it:        $XPAL_RUNTIME exec -it $XPAL_CONTAINER zsh
#   Refresh after a rebuild:    ./build.sh   (offers to rm + recreate)

IMAGE="$XPAL_IMAGE"
CONTAINER="$XPAL_CONTAINER"

# If it already exists, don't create a second one — restart and attach instead.
if "$XPAL_RUNTIME" container exists "$CONTAINER"; then
  echo "Container '$CONTAINER' already exists — starting and attaching."
  echo "(To rebuild from a changed Containerfile, use ./build.sh instead.)"
  exec "$XPAL_RUNTIME" start -ai "$CONTAINER"
fi

echo "Creating day-to-day container '$CONTAINER'..."
exec "$XPAL_RUNTIME" run -it --name "$CONTAINER" \
  --userns=keep-id \
  "${PORT_ARGS[@]}" \
  -v "$XPAL_HOST_SRC":/xpal-src:Z \
  -v "$XPAL_HOST_DATA":/xpal-data:Z \
  -v "$XPAL_HOST_AUTH":/xpal-auth:Z \
  "$IMAGE"
