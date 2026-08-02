# claudia

**Claude Introspective Analysis** — token usage, cost, and environmental impact
for Claude Code, from your own local session logs. Plus a containerized dev
environment and a git hook that tags every commit with the coding agent that
produced it.

```bash
uv tool install .            # or: cp claudia.py /usr/local/bin/claudia
claudia                      # per-project summary of turns, tokens, cost
claudia --by week --env      # weekly view with estimated energy/water/carbon
claudia index                # agent-agnostic session token ledger (Claude + OpenCode)
```

- **Offline-first** — reads `~/.claude/projects/**/*.jsonl` (and OpenCode's
  SQLite database for `claudia index`); no telemetry. Only `--verify` and the
  `haiku` classifier touch the network, and only with an explicit API key.
- **Stdlib-only, single file** — runs on `/usr/bin/python3`, no dependencies.

## Documentation

Start with the [docs index](docs/README.md):

| Doc | Covers |
|---|---|
| [installation.md](docs/installation.md) | Installing the CLI, container env, git hook |
| [usage.md](docs/usage.md) | Every command, filters, env-var overrides |
| [container-env.md](docs/container-env.md) | Containerized Claude Code + OpenCode environment |
| [agent-tagging.md](docs/agent-tagging.md) | `Coding-Agent:` commit trailers |
| [troubleshooting.md](docs/troubleshooting.md) | Common problems and fixes |
| [filing-issues.md](docs/filing-issues.md) | Filing issues + contributor workflow |

## Quick start

```bash
claudia                              # summary report
claudia --since 2026-07-01 --by week # weekly totals since July
claudia --env --cost                 # impact + cost breakdown
claudia --snapshot && claudia --install-cron   # keep daily snapshots

# container dev environment
cd containerconf && ./setup.sh && ./build.sh && ./run-daily.sh

# tag commits with their producing agent
claudia --install-git-hook
```

## Design constraints

- **stdlib-only, single file** — `claudia.py` runs on the system Python with no
  third-party dependencies.
- **No auth by default** — core reporting reads local files only.
- **Estimates are estimates** — cost/energy/water/carbon derive from published
  prices and hardware benchmarks ([ADR-002](docs/decisions/ADR-002-environmental-estimates.md));
  guidance, not billing.

## Development

Read [CLAUDE.md](CLAUDE.md) for conventions and [filing-issues.md](docs/filing-issues.md)
for the ADR → Issue → Todo → branch → PR workflow. Tests:

```bash
python3 -m unittest tests.test_claudia
```
