# claudia — tasks

## Shipped

- [x] Parse `~/.claude/projects/**/*.jsonl` for token usage
- [x] Summary report: turns, sessions, tokens, cost, models
- [x] `--by` grouping: project, day, week, month
- [x] `--since` date filter
- [x] `--project` path substring filter
- [x] `--models` model breakdown table
- [x] Environmental impact: energy (kWh), water (L), carbon (kg CO2)
- [x] Real-world energy analogs: lighting, water pumping, cooking (with stated assumptions)
- [x] `--env` flag for env metrics in table views
- [x] Rename `claude-usage` → `claudia` (Claude Introspective Analysis)
- [x] `--verify`: cross-check local totals vs Anthropic Admin API
- [x] `--api-key-id`: filter verify to a specific API key
- [x] Project structure: CLAUDE.md, ADRs, tasks/

## Upcoming

- [ ] `git init` and first commit
- [ ] `pyproject.toml` — proper Python package so `claudia` can be installed via `uv tool install`
- [ ] `--export csv` / `--export json` — machine-readable output for downstream use
- [ ] `claudia keys` subcommand — list API key IDs from the Admin API to make `--api-key-id` discoverable
- [ ] `claudia cost` — detailed cost breakdown using the `/v1/organizations/cost_report` endpoint
- [ ] Multi-machine support — aggregate JSONL from remote machines via SSH or shared mount
- [ ] `--watch` live mode — tail JSONL files and update the summary in place
- [ ] Week-over-week / month-over-month delta view
- [ ] Team usage rollup — aggregate by user across a shared workspace (requires Admin API)
- [ ] Tests — at minimum, fixture-based tests against sample JSONL to guard against schema drift

## Known issues / watch items

- JSONL schema is undocumented — `version` field on each entry can detect Claude Code upgrades
  that might change the format (currently tested on `2.1.x`)
- `--verify` delta will always be non-zero if sessions ran on multiple machines
- Admin API not available on AWS Marketplace Anthropic deployments
