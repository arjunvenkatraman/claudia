# Containerized dev environment

A minimal, containerized [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) +
[OpenCode](https://opencode.ai) environment on Debian 12 slim, running as a
non-root user with all credentials in a mounted host folder (never in the
image). Both agents are on PATH — `claude` or `opencode`, whichever you want in
a given session.

> The authoritative, current reference is `containerconf/README.md`. This page
> is the getting-started overview plus the pieces most people trip over.

## Layout

```
containerconf/
├── Containerfile      # image definition — the source of truth
├── entrypoint.sh      # runs on container start
├── .env.example       # documents the config keys (never sourced)
├── .env               # YOUR machine-specific config — gitignored, generated
├── setup.sh           # guided wizard -> writes .env
├── build.sh           # build image (rebuild + recreate after Containerfile changes)
├── run-daily.sh       # long-lived "day-to-day" container
├── run-daily-remote.sh# day-to-day + a remote (SharePoint) mount
├── run-ephemeral.sh   # throwaway --rm container, optional per-run remote
└── cleanup.sh         # remove day-to-day container + prune dangling images
```

## Get started

```bash
cd containerconf
./setup.sh        # guided: folders, UID, runtime, ports -> containerconf/.env
./build.sh        # build the image from the Containerfile
./run-daily.sh    # create and enter the day-to-day container
```

`setup.sh` prompts for each setting with a sensible default (host folders
default to `~/xpal-src`, `~/xpal-data`, `~/xpal-auth`; UID defaults to your
`id -u`; runtime auto-detects podman → docker), creates the folders, and writes
`containerconf/.env`. Re-run it any time to change paths, ports, or names — the
next container you create picks them up. For unattended setup:

```bash
XPAL_HOST_SRC="$HOME/code" ./setup.sh --yes
```

## Config keys (written by `setup.sh`)

| Key | Default | Meaning |
|---|---|---|
| `XPAL_RUNTIME` | auto (podman → docker) | Container runtime |
| `XPAL_IMAGE` | `xpal-claudia` | Image name |
| `XPAL_CONTAINER` | `xpal-dev` | Day-to-day container name |
| `XPAL_CONTAINER_REMOTE` | `xpal-dev-remote` | Remote-track container name |
| `XPAL_HOST_SRC` | `~/xpal-src` | Host code folder → `/xpal-src` |
| `XPAL_HOST_DATA` | `~/xpal-data` | Host data folder → `/xpal-data` |
| `XPAL_HOST_AUTH` | `~/xpal-auth` | Host credentials folder → `/xpal-auth` |
| `XPAL_HOST_UID` | `id -u` | UID for the container's `coder` user |
| `XPAL_PORTS` | `5001:5001 8001:8001 8080:8080` | Ports to publish to the host |
| `XPAL_HOST_REMOTE_DIR` | *(empty)* | Default remote (SharePoint) folder |

`.env` is machine-specific and gitignored — never commit it. `.env.example`
documents the shape and is committed on purpose.

## Two run tracks

**Day-to-day** — a persistent container you return to; mounts are fixed at creation:

```bash
./run-daily.sh                                  # first run creates it
$XPAL_RUNTIME start -ai $XPAL_CONTAINER         # re-enter later (e.g. podman start -ai xpal-dev)
$XPAL_RUNTIME exec -it $XPAL_CONTAINER zsh      # extra shell into it
```

**Ephemeral** — a fresh `--rm` container every launch; takes a remote folder per run:

```bash
./run-ephemeral.sh                                        # no remote
./run-ephemeral.sh "/path/to/SharePoint/ProjectA"         # mount this run
XPAL_REMOTE="/path/to/ProjectB" ./run-ephemeral.sh        # same, via env var
```

The remote is bound at `/xpal-data-remote`.

A container is pinned to the image it was created from. After editing the
Containerfile, run `./build.sh` — it rebuilds and offers to remove + recreate
the day-to-day container. Anything hand-installed in the old container is lost
on recreate; promote keepers to the Containerfile first (see below).

## Mounts

| Host (from `.env`) | Container | Purpose |
|---|---|---|
| `$XPAL_HOST_SRC` | `/xpal-src` | code (working dir) |
| `$XPAL_HOST_DATA` | `/xpal-data` | local data |
| `$XPAL_HOST_AUTH` | `/xpal-auth` | all credentials |
| *(ephemeral only)* | `/xpal-data-remote` | synced SharePoint folder |

Container-side paths are fixed; only the host side is per-machine.

## Authentication

Credentials are redirected to `/xpal-auth` via env vars set in the
Containerfile, so they persist on the host and never enter the image:

- **Claude Code** — `CLAUDE_CONFIG_DIR=/xpal-auth/claude`; run `claude` and log
  in once.
- **git** — `GIT_CONFIG_GLOBAL=/xpal-auth/git/gitconfig`; the entrypoint installs
  a credential helper storing tokens to `/xpal-auth/git/git-credentials`. Set
  your identity once: `git config --global user.name "..."`, `user.email "..."`.
- **npm** — `NPM_CONFIG_USERCONFIG=/xpal-auth/npm/npmrc`.

For SSH-based git, add a fourth mount onto the standard path
(`-v ~/xpal-auth/ssh:/home/coder/.ssh:Z`).

## Ports

`$XPAL_PORTS` are published to the host, so dev servers are reachable at
`localhost:<port>`. Under rootless Podman a container has **no host-routable
IP** — you can't reach it by IP; the ports must be published. **Servers must
bind to `0.0.0.0`, not `127.0.0.1`** (e.g. `flask run --host=0.0.0.0`,
`uvicorn --host 0.0.0.0`). Ports are fixed at container creation; changing them
means rebuild + recreate via `./build.sh`.

## Tracking hand-installed dependencies

Installs inside a running container are provisional — they vanish on
rebuild/recreate. To find what diverged before promoting to the Containerfile:

```bash
podman diff xpal-dev                        # files added/changed vs the image
grep " install " /var/log/dpkg.log | tail   # recently apt-installed packages (in-container)
npm ls -g --depth=0                         # global npm packages (in-container)
```

## Cleanup

```bash
./cleanup.sh
```

Removes the day-to-day container and prunes dangling `<none>` images left by
previous builds. Prompts first; never touches the current image, host data, or
git. Ephemeral containers use `--rm` and need no cleanup.

## What's inside

- Debian 12 (bookworm) slim
- Node.js 20 LTS, `git`, `ripgrep`
- zsh + oh-my-zsh (default shell)
- Claude Code (`claude`) and OpenCode (`opencode`)
- Python via `uv` (uv-managed CPython exposed as `python`/`python3`, plus
  `ipython` as a uv tool) — no apt python3
- A non-root `coder` user

## Requirements

Claude Code supports Debian 10+, needs Node.js 18+ and 4 GB+ RAM. See the
[Claude Code advanced setup docs](https://code.claude.com/docs/en/setup).
