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
- [x] `--serve` / `--port` — local web dashboard (http.server, auto-refresh)
- [x] `--snapshot` — save daily JSON to `~/.claude/claudia-snapshots/`
- [x] `--install-cron` — daily cron job to run `--snapshot` at 08:00
- [x] `--export json/csv` — machine-readable output; CSV combines with `--by`
- [x] `--watch [--interval]` — live summary mode, reruns every N seconds
- [x] `--delta {week,month}` — period-over-period cost and turn delta table
- [x] `--cost` — local cost breakdown by model × token type (input/output/cw/cr)
- [x] `--keys` — list Admin API key IDs (requires ANTHROPIC_ADMIN_KEY)
- [x] `pyproject.toml` — installable via `uv tool install .`; source renamed to `claudia.py`
- [x] `tests/test_claudia.py` — 23 fixture-based unit tests (pytest + unittest)

## Upcoming

- [x] Cross-filter composition — `--model` filter added (substring match); combines freely with `--since`, `--project` across all report commands including `--cost`, `--delta`, `--by`, `--watch`, `--serve`
- [x] `git init` and first commit (done)
- [x] `--by task-type` — classify sessions by work category; `--classifier rules` (offline regex) and `--classifier haiku` (claude-haiku-4-5, cached); taxonomy configurable via `~/.claude/claudia-taxonomy.json`
- [x] Guided portable setup — `containerconf/setup.sh` wizard generates a gitignored `.env`; run/build/cleanup scripts source it; env-var path overrides in `claudia.py` (issue #6, ADR-004)
- [x] Pre-publication cleanup protocol — `scripts/scrub-public.sh` + `docs/public-release.md`; untracked `.DS_Store` / `.claude/settings.local.json`
- [x] Agent-attributed commits — `prepare-commit-msg` hook appends a `Coding-Agent: claude|opencode|manual` trailer; installed via `scaffold.py init` / `--install-git-hook` and `claudia --install-git-hook` (issue #8, ADR-005)
- [x] User documentation — `docs/` with installation, usage, container-env, agent-tagging, troubleshooting, and filing-issues (issue #10)
- [ ] Coder session index — `claudia index`: agent-agnostic per-session ledger (input/genuine-output/junk tokens + agent + model) from Claude Code JSONL + OpenCode SQLite; content-based summary fallback (issue #12, ADR-006)
- [ ] OpenCode session integrity — confirm live/partial session rows in `opencode.db` and whether `session` token fields ever lag (watch item)
- [ ] Multi-machine support — aggregate JSONL from remote machines via SSH or shared mount
- [ ] Team usage rollup — aggregate by user across a shared workspace (requires Admin API)
- [ ] Consider splitting `claudia.py` (now ~870 lines) into `_core.py` + `_admin.py` + entrypoint

## Known issues / watch items

- JSONL schema is undocumented — `version` field on each entry can detect Claude Code upgrades
  that might change the format (currently tested on `2.1.x`)
- `--verify` delta will always be non-zero if sessions ran on multiple machines
- Admin API not available on AWS Marketplace Anthropic deployments
