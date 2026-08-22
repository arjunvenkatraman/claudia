# Lessons learned

## 2026-05-12 — Initial build

- **JSONL schema**: Every Claude Code assistant turn in `~/.claude/projects/**/*.jsonl`
  carries a `message.usage` object with full token breakdown including cache split. The
  `type: "assistant"` field identifies these entries. Filter out `model: "<synthetic>"` —
  those appear in internal tool-use plumbing and carry no real usage data.

- **Cache tokens dominate**: For heavy Claude Code use, `cache_read_input_tokens` is
  typically 50-100× larger than `output_tokens`. Over 3 weeks: 282M cache reads vs 3.3M
  output tokens. Pricing matters: cache reads at $0.30/MTok vs output at $15/MTok means
  the cache is saving very significant cost.

- **Output tokens drive energy**: Despite cache reads being the largest token count,
  energy consumption is dominated by output tokens (0.39 J each) because each output
  token requires a full autoregressive forward pass. Cache reads are ~0.02 J each.

- **Admin API requires Admin key**: The `/v1/organizations/usage_report/messages` endpoint
  rejects regular user API keys (`sk-ant-api...`) with a 403. It requires an Admin key
  (`sk-ant-admin...`) provisioned at console.anthropic.com → Settings → Admin API Keys.
  Org admin role required to create these.

- **API field for cache writes**: In the Admin API response, cache creation is split into
  `cache_creation.ephemeral_1h_input_tokens` and `cache_creation.ephemeral_5m_input_tokens`.
  The local JSONL rolls these into a single `cache_creation_input_tokens` field. Sum both
  API fields to match the local figure.

- **Anthropic has no per-token environmental data**: No official Anthropic figure exists
  for energy per token. The best public source is TokenPowerBench (arxiv 2512.03024) at
  0.39 J/output token on H100 hardware. Water and carbon are derived from this via
  industry-average data-center WUE and US grid intensity.

## 2026-08-22 — `Model:` trailer (ADR-007)

- **No env var reliably names the running model.** `ANTHROPIC_MODEL`/`CLAUDE_MODEL` are
  override *inputs*, not the effective model echoed back — unset in a normal session even
  though a specific model is definitely running. Had to read it from the agent's own
  session log instead of trusting the environment, unlike agent identity (ADR-005), which
  genuinely is a stable env marker.
- **Claude Code JSONL filenames are the session id** (`<sessionId>.jsonl`), so looking up
  "the model for *this* session" via `CLAUDE_CODE_SESSION_ID` is a direct glob, not a scan
  of `read_claude_sessions()`'s full history — much cheaper for something that runs on
  every commit.
- **OpenCode's `session.model` column is polymorphic**: sometimes a plain string, sometimes
  a JSON blob `{"id", "providerID"}`. `_opencode_session_record` already handled this for
  `claudia index`; the new `--current-model` path needed the same parsing (`_opencode_model_id`)
  or it would've printed the raw JSON blob into commit trailers.
- **`claude_dir()` was silently broken in this project's own container setup**: it checked
  only `CLAUDIA_CLAUDE_DIR`, never `CLAUDE_CONFIG_DIR` (the var `docs/container-env.md`
  documents this container as actually setting, to `/xpal-auth/claude`). Every claudia
  command — not just the new one — was reading an empty default `~/.claude` and reporting
  "No matching usage data found." the whole time. Found only because `--current-model`
  returned `unknown` when the live JSONL clearly had the data. Worth periodically sanity
  checking claudia's own commands actually see data in whatever environment they're
  supposedly supported in, rather than trusting that passing tests means it works live.
