# Usage

`claudia` reads your Claude Code session logs (`~/.claude/projects/**/*.jsonl`)
and reports what those sessions consumed. Everything below runs offline and
against local files unless noted.

```bash
claudia [options]
```

Run `claudia --help` any time for the canonical flag list.

## The default report

```bash
claudia
```

Shows a per-project summary: turns, sessions, tokens (input/output/cache), and
estimated cost, ordered by usage. It scans every JSONL under `~/.claude/projects/`
and is your starting point for anything else.

When a session's messages carry no provider `usage` block, claudia now falls
back to estimating tokens from message content (≈ chars ÷ 4.0) so the report is
never empty — those turns are flagged with a note in the output. Use
`--verify` for provider-accurate numbers (it reads only provider-flagged turns).

## The coder session index — `index`

```bash
claudia index                     # append new per-session rows to the ledger
claudia index --json              # print rows as JSON instead of appending
claudia index --out /path/to/dir  # write the full ledger to /path/to/dir/coder-index.jsonl
claudia index --agent opencode    # filter to one agent (claude | opencode)
```

Builds the agent-agnostic per-session ledger (ADR-006): one row per session with
input / genuine-output / junk tokens, agent, model, timestamps, and exact char
counts. Reads two sources and normalizes them into one schema
(`xpal-coder-index/v1`):

- **Claude Code** — `~/.claude/projects/**/*.jsonl` (content-based; provider
  `usage` counts when present)
- **OpenCode** — the read-only SQLite database at
  `~/.local/share/opencode/opencode.db` (provider token counts)

Rows are appended to `~/.claude/claudia-index/coder-index.jsonl`, deduplicated
by `session_id`. Junk = aborted/interrupted generations only; OpenCode doesn't
track aborts, so its rows carry `junk_tokens: null`. Counting is purely local —
no model calls, no extra tokens, no prompt text, no file contents. The ledger is
the input to bigtokentask's observed-cost index (see `docs/decisions/ADR-006`).

## Filters

| Flag | What it does | Example |
|---|---|---|
| `--since YYYY-MM-DD` | Only usage on/after this date | `claudia --since 2026-07-01` |
| `--project PATH` | Only that project (substring match on path) | `claudia --project xpal-src` |
| `--model NAME` | Only that model (substring, e.g. `opus`, `sonnet`, `haiku`) | `claudia --model sonnet` |

Filters compose: `claudia --since 2026-07-01 --project claudia --model opus`.

## Grouping — `--by`

```bash
claudia --by project      # per-project totals (default grouping)
claudia --by day          # totals per calendar day
claudia --by week         # totals per ISO week
claudia --by month        # totals per calendar month
claudia --by task-type    # grouped by task category (see below)
```

### Task-type classification

`--by task-type` buckets sessions into categories. Two backends:

- **`rules`** (default, offline) — a regex taxonomy over session titles and
  prompt text. Nothing leaves your machine.
- **`haiku`** — sends prompt text to `claude-haiku-4-5` for classification.
  Requires `ANTHROPIC_API_KEY` (a *user* key, unlike `--verify` which needs an
  Admin key) and asks for confirmation before the first (paid) batch — pass
  `--yes` to skip the prompt.

```bash
claudia --by task-type --classifier haiku --yes
```

The taxonomy is configurable: drop a `claudia-taxonomy.json` in `~/.claude/`
and it is loaded instead of the built-in one.

## Tables and breakdowns

```bash
claudia --models        # per-model breakdown (tokens, cost)
claudia --cost          # cost detail by model and token type (input/cache/output)
claudia --env           # estimated energy (kWh), water (L), carbon (kg CO2e)
claudia --delta week    # period-over-period delta for cost and turns
claudia --delta month
```

`--env` numbers come from published hardware and grid benchmarks (see
[ADR-002](../docs/decisions/ADR-002-environmental-estimates.md)) — guidance,
not metering.

## Verifying against the Admin API

```bash
ANTHROPIC_ADMIN_KEY=sk-ant-admin... claudia --verify
ANTHROPIC_ADMIN_KEY=sk-ant-admin... claudia --verify --api-key-id apikey_01Abc...
```

Cross-checks local JSONL totals against the Anthropic Admin API. Requires an
**Admin** key (not a user key) and an org that has access to Admin API billing
data — orgs that obtained Anthropic API via an AWS/other marketplace contract
don't get it (you'll see a 403). Repeat `--api-key-id` to include multiple keys.

```bash
ANTHROPIC_ADMIN_KEY=sk-ant-admin... claudia --keys    # list your API key IDs
```

## Data lifecycle

```bash
claudia --snapshot          # save ~/.claude/claudia-snapshots/YYYY-MM-DD.json
claudia --install-cron      # install daily jobs: 08:00 snapshot, 08:30 index
claudia --export json       # dump everything to stdout as JSON
claudia --export csv        # CSV; combine with --by for grouped CSV
```

Snapshots let you keep daily totals even after Claude Code prunes session logs.

## Web dashboard and live mode

```bash
claudia --serve             # dashboard on http://localhost:7777
claudia --serve --port 9000
claudia --watch             # reprint summary every 5s (live mode)
claudia --watch --interval 30
```

## Environment variable overrides

Everything in `claudia.py` that touches the filesystem or network honors an env
var, so it can run against relocated data without editing the file:

| Variable | Default | Purpose |
|---|---|---|
| `CLAUDIA_CLAUDE_DIR` | `~/.claude` | Where Claude Code logs + caches live |
| `CLAUDIA_SNAPSHOT_DIR` | `<claude>/claudia-snapshots` | Snapshot output |
| `CLAUDIA_LABELS_FILE` | `<claude>/claudia-labels.json` | Task-type label cache |
| `CLAUDIA_TAXONOMY_FILE` | `<claude>/claudia-taxonomy.json` | Task taxonomy override |
| `CLAUDIA_INDEX_DIR` | `<claude>/claudia-index` | Where `index` appends `coder-index.jsonl` |
| `CLAUDIA_OPENCODE_DB` | `~/.local/share/opencode/opencode.db` | OpenCode session DB for `index` |
| `CLAUDIA_AGENT` | *unset* | Default agent filter for `index` (`claude`/`opencode`) |
| `CLAUDIA_BIN` | auto-detected | Path to the `claudia` binary (for cron/serve) |
| `CLAUDIA_MONITOR_LOG` | *unset* | Append an audit line per run (used by the container) |
| `ANTHROPIC_ADMIN_KEY` | *unset* | Admin API key for `--verify` / `--keys` |
| `ANTHROPIC_API_KEY` | *unset* | User API key for the `haiku` classifier |

Example: analyze logs copied from another machine:

```bash
CLAUDIA_CLAUDE_DIR=/backup/claude-logs claudia --by week
```

## Common examples

```bash
# This month by project, with environmental impact
claudia --by project --since "$(date +%Y-%m-01)" --env

# Weekly cost trend over the last two months
claudia --by week --since 2026-06-01 --cost

# Just this repo's sonnet usage since June
claudia --project claudia --model sonnet --since 2026-06-01

# CSV for a spreadsheet, grouped by task type
claudia --by task-type --export csv > task-breakdown.csv

# Verify local totals, filtered to one API key
ANTHROPIC_ADMIN_KEY=sk-ant-admin... claudia --verify --api-key-id apikey_01Abc...
```
