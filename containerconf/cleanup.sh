#!/usr/bin/env bash
set -e

# --- Cleanup --------------------------------------------------------------
# Removes the day-to-day container and reclaims space from previous builds.
#
# Each `./build.sh` produces a new xpal-claudia:latest and leaves the PREVIOUS
# image untagged ("dangling", shown as <none>). Those pile up over rebuilds.
# This prunes them. It does NOT touch the current image, your host mounts
# (xpal-src / xpal-data / xpal-auth), or anything in git — only container
# state and orphaned image layers.
#
# Ephemeral containers (run-ephemeral.sh) use --rm and clean themselves up,
# so there's nothing to remove for that track.

IMAGE="xpal-claudia"
CONTAINER="xpal-dev"

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
if podman container exists "$CONTAINER"; then
  podman rm -f "$CONTAINER"
  echo "Removed container '$CONTAINER'."
else
  echo "No '$CONTAINER' container to remove."
fi

# Prune dangling images (untagged layers from prior builds). Safe: tagged
# images, including xpal-claudia:latest, are kept.
echo "Pruning dangling images..."
podman image prune -f

echo
echo "Current xpal-claudia images:"
podman images "$IMAGE" || true

echo "Done."
