#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# --- Cleanup --------------------------------------------------------------
# Removes the day-to-day container and reclaims space from previous builds.
#
# Each `./build.sh` produces a new image and leaves the PREVIOUS one untagged
# ("dangling", shown as <none>). Those pile up over rebuilds. This prunes
# them. It does NOT touch the current image, your host mounts, or anything in
# git — only container state and orphaned image layers.
#
# Ephemeral containers (run-ephemeral.sh) use --rm and clean themselves up,
# so there's nothing to remove for that track.

IMAGE="$XPAL_IMAGE"
CONTAINER="$XPAL_CONTAINER"

echo "This will:"
echo "  - remove the '$CONTAINER' container (any hand-installed state is lost)"
echo "  - prune dangling <none> images left behind by previous builds"
echo "It will NOT delete the current '$IMAGE' image or your host data."
echo
read -r -p "Proceed? [y/N] " reply
case "$reply" in
  [yY]|[yY][eE][sS]) ;;
  *) echo "Aborted."; exit 0 ;;
esac

# Remove the named container if present (-f stops it first if running).
if "$XPAL_RUNTIME" container exists "$CONTAINER"; then
  "$XPAL_RUNTIME" rm -f "$CONTAINER"
  echo "Removed container '$CONTAINER'."
else
  echo "No '$CONTAINER' container to remove."
fi

# Prune dangling images (untagged layers from prior builds). Safe: tagged
# images, including the current image, are kept.
echo "Pruning dangling images..."
"$XPAL_RUNTIME" image prune -f

echo
echo "Current $IMAGE images:"
"$XPAL_RUNTIME" images "$IMAGE" || true

echo "Done."
