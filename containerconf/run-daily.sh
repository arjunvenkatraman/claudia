#!/usr/bin/env bash
set -e

# --- Day-to-day track -----------------------------------------------------
# A long-lived, named container with stable mounts and NO remote folder.
# Create it once; re-enter it across sessions. Mounts are fixed at creation.
#
#   First run (creates it):     ./run-daily.sh
#   Re-enter later:             podman start -ai xpal-dev
#   Extra shell into it:        podman exec -it xpal-dev zsh
#   Refresh after a rebuild:    ./build.sh   (offers to rm + recreate)

IMAGE="xpal-claudia"
CONTAINER="xpal-dev"

# If it already exists, don't create a second one — restart and attach instead.
if podman container exists "$CONTAINER"; then
  echo "Container '$CONTAINER' already exists — starting and attaching."
  echo "(To rebuild from a changed Containerfile, use ./build.sh instead.)"
  exec podman start -ai "$CONTAINER"
fi

echo "Creating day-to-day container '$CONTAINER'..."
exec podman run -it --name "$CONTAINER" \
  --userns=keep-id \
  -p 5001:5001 \
  -p 8001:8001 \
  -p 8080:8080 \
  -v "$HOME/Development/xpal-src":/xpal-src:Z \
  -v "$HOME/Development/xpal-data":/xpal-data:Z \
  -v "$HOME/Development/xpal-auth":/xpal-auth:Z \
  "$IMAGE"
