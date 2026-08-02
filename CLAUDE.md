# claudia — development guidelines

## What this project is

**claudia** — Claude Introspective Analysis.

A CLI tool that reads Claude Code's local session logs (`~/.claude/projects/**/*.jsonl`)
to report token usage, estimated cost, and environmental impact. Intended to grow into a
broader suite of Claude self-analysis and observability tools.

The installed binary lives at `/usr/local/bin/claudia`. The source is the single file
`/xpal-src/claudia/claudia.py` (`.py` extension required for Python packaging).

## Repository layout

```
claudia/
├── claudia.py               # The CLI — single Python script, stdlib only
├── pyproject.toml           # Package metadata for uv tool install
├── CLAUDE.md                # This file
├── README.md                # User-facing entry point, links to docs/
├── docs/
│   ├── README.md            # Docs index
│   ├── installation.md      # Install CLI, container env, git hook
│   ├── usage.md             # Full CLI reference
│   ├── container-env.md     # Containerized dev environment
│   ├── agent-tagging.md     # Coding-Agent commit trailers
│   ├── troubleshooting.md   # Common problems and fixes
│   ├── filing-issues.md     # How to file issues + contribute
│   └── decisions/           # ADRs — read before changing core approach
│       ├── ADR-001-local-jsonl-parsing.md
│       ├── ADR-002-environmental-estimates.md
│       ├── ADR-003-admin-api-verify.md
│       ├── ADR-004-guided-portable-setup.md
│       ├── ADR-005-agent-git-trailers.md
│       └── ADR-006-coder-session-index.md
├── tasks/
│   ├── todo.md              # Current and upcoming work
│   └── lessons.md           # Dated discoveries and gotchas
└── tests/
    └── test_claudia.py      # Fixture-based unit tests
```

## Design constraints

- **stdlib only** — no third-party dependencies. `claudia` must run with the system Python
  (`/usr/bin/python3`) without a virtualenv. Every import must be from the standard library.
- **Single file** — the entire tool is `claudia.py`. At ~870 lines it is approaching the
  split threshold — consider extracting Admin API helpers if the file grows further.
- **No auth by default** — the core reporting commands read local files only. The `--verify`
  command is the only path that touches the network, and it requires an explicit env var.
- **Offline-first** — all estimates (cost, energy, water, carbon) are computed locally from
  the JSONL data. No telemetry, no callbacks.

## Adding a new command

1. Add a `cmd_<name>(entries, args)` function
2. Add a `--<name>` argument to the argparse block in `main()`
3. Wire it into the dispatch block in `main()`
4. Write an ADR in `docs/decisions/` if the approach involves a non-obvious design choice
5. Add the task to `tasks/todo.md` as `[x]` when shipped

## Coding standards

- Python 3.10+. Use `match` where it reads better than `if/elif` chains.
- Type hints on all function signatures. No `Any`.
- Format strings over concatenation.
- Constants at the top of the file in ALL_CAPS — update them when sources change.
- Every estimate shown to the user must cite its source inline (comment or note in output).

## Updating constants

Environmental and pricing constants live at the top of `claudia`:

| Constant | Source | When to update |
|---|---|---|
| `PRICING` | Anthropic pricing page | Model price changes |
| `ENERGY_J` | TokenPowerBench / Luccioni et al. 2023 | New hardware benchmarks |
| `WATER_L_PER_KWH` | Li et al. 2023 | Significant WUE improvements |
| `CARBON_KG_PER_KWH` | EPA / Ember annual grid report | Annually |

After updating constants, copy to `/usr/local/bin/claudia`:
```bash
cp /xpal-src/claudia/claudia.py /usr/local/bin/claudia
```

## Verifying against the Anthropic Admin API

```bash
# Org-wide
ANTHROPIC_ADMIN_KEY=sk-ant-admin... claudia --verify

# Filtered to your key (find ID at console.anthropic.com → API Keys)
ANTHROPIC_ADMIN_KEY=sk-ant-admin... claudia --verify --api-key-id apikey_01Abc...
```

Requires an Admin API key — not a regular user key. See ADR-003.

## ADRs

Read `docs/decisions/` before changing the data source, estimation methodology, or
API integration approach. Key decisions:

- ADR-001: Read local JSONL rather than making API calls for core reporting
- ADR-002: Environmental impact estimation sources and methodology
- ADR-003: Anthropic Admin API for cross-verification
- ADR-006: Coder session index (`claudia index`) — agent-agnostic per-session
  token ledger; read it before touching the ledger schema or counting logic

## Git workflow

- Conventional commits: `feat:`, `fix:`, `docs:`, `chore:`
- Every commit carries a `Coding-Agent:` trailer (`claude`, `opencode`, or
  `manual`) via the `prepare-commit-msg` hook. Install it in a repo with
  `claudia --install-git-hook [PATH]`.
- After any change to `claudia.py`, copy to `/usr/local/bin/claudia`
- Do not commit API keys or Admin keys
