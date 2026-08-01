# xpal-claudia — containerized Claude Code

A minimal, containerized [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
environment on Debian slim. Runs as a non-root user, uses zsh + oh-my-zsh, and
keeps all credentials in a mounted host folder (never in the image).

The **Containerfile is the source of truth.** The image is rebuilt from it; you
never `podman commit` a running container into your build chain. Both run modes
below start from the same freshly built image.

## Prerequisites

Create the host folders once (the auth subfolders let the tools write configs
on first use):

```bash
mkdir -p ~/Development/xpal-src ~/Development/xpal-data
mkdir -p ~/Development/xpal-auth/{claude,git,npm}
```

## Build

```bash
./build.sh          # builds the image; offers to refresh the day-to-day container
# or plainly:
podman build -t xpal-claudia .
```

## Two run tracks

### 1. Day-to-day (long-lived, named, stable mounts)

A persistent container you return to. Mounts are fixed at creation. No remote.

```bash
./run-daily.sh                      # first run creates 'xpal-dev'
podman start -ai xpal-dev           # re-enter later
podman exec -it xpal-dev zsh        # open an extra shell into it
```

A container is pinned to the image it was created from. After changing the
Containerfile, run `./build.sh` — it rebuilds and offers to remove + recreate
`xpal-dev` so it picks up the new image. (Anything hand-installed in the old
container is lost on recreate — promote keepers to the Containerfile first.)

### 2. Ephemeral (throwaway, optional per-run SharePoint mount)

A fresh `--rm` container every launch, so it always uses the latest image and
can take a different remote folder each time.

```bash
./run-ephemeral.sh                              # no remote
./run-ephemeral.sh "/path/to/SharePoint/ProjectA"   # mount ProjectA this run
XPAL_REMOTE="/path/to/ProjectB" ./run-ephemeral.sh  # same, via env var
```

The remote is bound at `/xpal-data-remote`.

**SharePoint prerequisite:** the library must be **synced to a local folder**
by the OneDrive/SharePoint sync client — a bind mount can only point at a path
that already exists on this filesystem. On macOS that's usually under
`~/Library/CloudStorage/OneDrive-<org>/...`. If the library is *not* synced
locally, a bind mount can't reach it; you'd need `rclone` inside the container
instead (different setup). If files appear missing inside the container despite
the folder existing, the sync client may be showing online-only placeholders —
set the folder to "always keep on this device."

## Mounts

| Host path                     | Container path      | Purpose               |
|-------------------------------|---------------------|-----------------------|
| `~/Development/xpal-src`      | `/xpal-src`         | code (working dir)    |
| `~/Development/xpal-data`     | `/xpal-data`        | local data            |
| `~/Development/xpal-auth`     | `/xpal-auth`        | all credentials       |
| *(per-run, ephemeral only)*   | `/xpal-data-remote` | synced SharePoint     |

`--userns=keep-id` (set in both run scripts) maps the container's `coder` user
to your host user so it can read/write the bind-mounted host folders under
rootless Podman. Without it you'll get permission errors on the mounts.

## Ports

The day-to-day container publishes `5000`, `8000`, and `8080` to the host
(`-p` in `run-daily.sh`), so a dev server on those ports is reachable at
`localhost:<port>` on your machine. Under rootless Podman a container has no
host-routable IP, so ports must be published explicitly — you can't hit the
container by IP.

**Servers must bind to `0.0.0.0`, not `127.0.0.1`,** or the published port has
nothing to connect through (e.g. `flask run --host=0.0.0.0`,
`uvicorn --host 0.0.0.0`). Ports are fixed at container creation; changing them
means a rebuild + recreate (`./build.sh`).

## Authentication

All credentials are redirected to `/xpal-auth` via environment variables set in
the Containerfile, so they persist on the host and never enter the image:

- **Claude Code** — `CLAUDE_CONFIG_DIR=/xpal-auth/claude` (holds
  `.credentials.json` etc.). Run `claude` and log in once.
- **git** — `GIT_CONFIG_GLOBAL=/xpal-auth/git/gitconfig`; the entrypoint sets a
  credential helper storing tokens to `/xpal-auth/git/git-credentials`. Set your
  identity once (persists): `git config --global user.name "..."` and
  `user.email "..."`.
- **npm** — `NPM_CONFIG_USERCONFIG=/xpal-auth/npm/npmrc`.

For SSH-based git, add a fourth mount onto the standard path, e.g.
`-v ~/Development/xpal-auth/ssh:/home/coder/.ssh:Z`.

**Never commit credentials.** The `.gitignore` excludes common secret files;
credentials live in the mounted host folder, not the repo or the image.

## Tracking hand-installed dependencies

Installs made inside a running container are provisional — they vanish on
rebuild/recreate. To see what diverged from the image before promoting to the
Containerfile:

```bash
podman diff xpal-dev                      # files added/changed vs the image
# inside the container:
grep " install " /var/log/dpkg.log | tail # recently apt-installed packages
npm ls -g --depth=0                        # global npm packages
```

Fold keepers into the Containerfile's `apt-get install` / `npm install -g`
lines, commit, then `./build.sh`.

## Cleanup

```bash
./cleanup.sh
```

Removes the `xpal-dev` container and prunes dangling `<none>` images left behind
by previous builds (each `./build.sh` orphans the prior image). Prompts before
acting; never touches the current image, your host data, or git. Ephemeral
containers use `--rm` and need no cleanup.

## What's inside

- Debian 12 (bookworm) slim base
- Node.js 20 LTS, `git`, `ripgrep`
- zsh + oh-my-zsh (default shell)
- Claude Code (`@anthropic-ai/claude-code`)
- Python toolchain: `uv` (owns Python — no apt python3), a uv-managed CPython
  exposed as `python`/`python3`, and `ipython` as a uv tool
- A non-root `coder` user

## Requirements

Claude Code officially supports Debian 10+, needs Node.js 18+, and 4 GB+ RAM.
See the [advanced setup docs](https://code.claude.com/docs/en/setup).
