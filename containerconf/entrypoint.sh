#!/usr/bin/env bash
set -e

# Runtime initialization.
#
# These directories live INSIDE the /xpal-auth bind mount, so they can only be
# created after the mount exists — i.e. now, at container start. Creating them
# at build time would be pointless: the runtime mount masks anything the image
# baked into this path.
mkdir -p /xpal-auth/claude /xpal-auth/git /xpal-auth/npm

# Point git's credential store at the mounted auth dir (idempotent — safe to
# run on every start). Writes to $GIT_CONFIG_GLOBAL, which lives in the mount,
# so it persists across rebuilds.
git config --global credential.helper "store --file=/xpal-auth/git/git-credentials"

# Hand off to whatever CMD was given (zsh, by default).
exec "$@"
