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
claudia --install-cron      # install a daily 08:00 cron job that runs --snapshot
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
