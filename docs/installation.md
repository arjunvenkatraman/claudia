# Installation

This covers three things you can install from this repository:

1. The **`claudia` CLI** — usage/cost/environment reporting from Claude Code logs.
2. The **containerized dev environment** — Claude Code + OpenCode in a Podman/
   Docker container with your code and credentials mounted in.
3. The **`Coding-Agent` git hook** — tags every commit with which agent wrote it.

## Prerequisites

- **Python 3.10+** on the system (`/usr/bin/python3` works; no venv required).
- **Claude Code session logs** for the CLI to report on. These exist once you
  have used [Claude Code](https://code.claude.com) on this machine — they live
  in `~/.claude/projects/**/*.jsonl`. The CLI reads local files only.
- **Container tools** (only for the container environment): `podman`
  (preferred, rootless) or `docker`.
- **git** for the commit hook.

## 1. Install the CLI

Two equivalent ways:

```bash
# Option A — package install with uv (recommended)
uv tool install .          # run from a clone of this repo

# Option B — manual copy (matches the repo's own workflow)
cp claudia.py /usr/local/bin/claudia
```

Verify:

```bash
claudia --help
```

> `claudia.py` keeps the `.py` extension because the packaging metadata
> (`pyproject.toml`) needs it. The installed binary is that same single file,
> so the manual copy behaves identically to the packaged install.

### Optional: helper files

- **Snapshots** land in `~/.claude/claudia-snapshots/` (created on first
  `--snapshot`).
- **Task-type labels** are cached in `~/.claude/claudia-labels.json`.
- **Task taxonomy** can be overridden via `~/.claude/claudia-taxonomy.json`
  (see [usage.md](usage.md#task-type-classification)).
- **Daily snapshot cron** — `claudia --install-cron` adds a 08:00 crontab job.

## 2. Install the container environment

See [container-env.md](container-env.md) for the full guide. In short:

```bash
cd containerconf
./setup.sh          # guided: paths, UID, runtime, ports -> writes containerconf/.env
./build.sh          # build the image from the Containerfile
./run-daily.sh      # create and enter the day-to-day container
```

Requirements on the host: `podman` (or `docker`), a code folder, a data folder,
and a credentials folder. `setup.sh` asks for all of these and creates them.

## 3. Install the `Coding-Agent` git hook

The hook appends a `Coding-Agent: claude|opencode|manual` trailer to every
commit. Install it per repository in one of three ways:

```bash
# A) From the claudia CLI (works even after the manual /usr/local/bin copy)
claudia --install-git-hook                 # current directory
claudia --install-git-hook /path/to/repo   # specific repo

# B) Via the project-scaffold skill (also sets up CLAUDE.md, tasks/, docs/decisions/)
python3 skills/project-scaffold/scaffold.py /path/to/repo --install-git-hook

# C) It is installed automatically when you scaffold a new project:
python3 skills/project-scaffold/scaffold.py /path/to/new-project \
    --name myproject --summary "What it does"
```

See [agent-tagging.md](agent-tagging.md) for how detection works and how to
verify it.

## Post-install checks

| Check | Command | Expected |
|---|---|---|
| CLI runs | `claudia --help` | usage text |
| Logs are found | `claudia` | a summary (even if 0 turns) |
| Container image | `podman images xpal-claudia` | image present after `./build.sh` |
| Hook installed | `ls .git/hooks/prepare-commit-msg` | file exists and is executable |
