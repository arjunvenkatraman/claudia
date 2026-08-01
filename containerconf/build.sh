#!/usr/bin/env bash
set -e

# Rebuild the xpal-claudia image from the Containerfile.
#
# After a Containerfile change the ritual is: rebuild -> rm -> recreate the
# named container. Ephemeral runs (run-ephemeral.sh) pick up the new image
# automatically, so only the day-to-day named container needs a manual refresh.

IMAGE="xpal-claudia"
CONTAINER="xpal-dev"

echo "Building $IMAGE from Containerfile..."
podman build -t "$IMAGE" .

# If the day-to-day named container exists, offer to recreate it so it picks
# up the freshly built image (a container is pinned to the image as it was at
# creation — rebuilding the image does NOT update an existing container).
if podman container exists "$CONTAINER"; then
  echo
  echo "The day-to-day container '$CONTAINER' is running the OLD image."
  read -r -p "Remove and recreate it from the new image? [y/N] " reply
  case "$reply" in
    [yY]|[yY][eE][sS])
      podman rm -f "$CONTAINER"
      echo "Removed '$CONTAINER'. Recreate it with:  ./run-daily.sh"
      echo "(Reminder: anything hand-installed in the old container is gone —"
      echo " make sure keepers were promoted into the Containerfile first.)"
      ;;
    *)
      echo "Left '$CONTAINER' as-is. It will keep running the old image until"
      echo "you remove and recreate it."
      ;;
  esac
fi

echo "Done."
