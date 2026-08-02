# claudia — documentation

**claudia** (Claude Introspective Analysis) reads your local Claude Code session
logs and reports token usage, estimated cost, and environmental impact. It also
ships a containerized development environment and a git hook that tags every
commit with the coding agent that produced it.

## Contents

| Doc | What it covers |
|---|---|
| [installation.md](installation.md) | Installing the CLI, the container environment, and the git hook |
| [usage.md](usage.md) | Every `claudia` command, filters, env-var overrides, examples |
| [container-env.md](container-env.md) | The containerized Claude Code + OpenCode dev environment: setup, build, run tracks, auth, ports |
| [agent-tagging.md](agent-tagging.md) | The `Coding-Agent:` commit trailer and its `prepare-commit-msg` hook |
| [troubleshooting.md](troubleshooting.md) | Common problems and fixes for the CLI, container, and hook |
| [filing-issues.md](filing-issues.md) | How to report issues and the contributor workflow (ADR → Issue → Todo → branch → PR) |

## Quick start

```bash
# 1. Install the CLI (see installation.md for alternatives)
uv tool install .          # from a clone of this repo
# or: cp claudia.py /usr/local/bin/claudia

# 2. Run your first report — reads ~/.claude/projects/**/*.jsonl
claudia
claudia --by week --since 2026-05-01 --env

# 3. Container environment (needs podman or docker)
cd containerconf && ./setup.sh && ./build.sh && ./run-daily.sh

# 4. Agent tagging (per repo, so git history records which agent committed)
claudia --install-git-hook
```

## Design constraints (read before relying on it)

- **Offline-first.** Core reports read local files only; no telemetry. Only
  `--verify` and the `haiku` classifier touch the network, and only with an
  explicit API key.
- **stdlib-only.** `claudia` runs on the system Python (`/usr/bin/python3`)
  with no third-party dependencies.
- **Estimates are estimates.** Cost, energy, water, and carbon are computed
  from published model prices and hardware benchmarks (see the constants at
  the top of `claudia.py` and the ADRs). Treat them as guidance, not billing.
