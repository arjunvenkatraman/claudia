# ADR-006: Coder session index (agent-agnostic token ledger)

**Status:** Accepted

## Context

claudia's core reporting depends on the Anthropic `usage` block inside each
assistant message — `load_entries` skips any message without one. Model
providers have stopped providing this per-message detail, so claudia now
reports nothing for real sessions.

bigtokentask's index of task cost/time needs empirical grounding: its
`throughput.yaml` layer is provisional, and its fertility figures are
benchmark-based. The natural source of data is real developer sessions with
coding agents (Claude Code, OpenCode) against frontier API models.

We need a cheap, passive, agent-agnostic per-session token ledger —
input tokens, genuine output tokens, and junk tokens — tagged with agent and
model, from which cost / energy / water can be inferred post-process. Two hard
constraints: no extra model tokens spent on monitoring, and no slowdown to
developers.

OpenCode persists sessions in a SQLite database
(`~/.local/share/opencode/opencode.db`) whose `session` table already records
per-session `tokens_input`, `tokens_output`, `tokens_reasoning`,
`tokens_cache_read`, `tokens_cache_write`, `cost`, `model`, `agent`, and
timestamps. Claude Code persists JSONL transcripts whose per-message `usage`
is now often absent, but whose message content (text / thinking / tool_use
blocks) is still present.

## Decision

Add a `claudia index` command that reads both sources, normalizes them into a
single ledger schema (`xpal-coder-index/v1`), and appends one row per session
to an append-only JSONL ledger. Add a content-based fallback so the existing
summary still reports when provider `usage` is absent.

### Ledger schema (`xpal-coder-index/v1`)

Per session, one JSONL row:

| Field | Meaning |
|---|---|
| `schema` | `xpal-coder-index/v1` |
| `session_id` | stable source session id |
| `source` | `claude` \| `opencode` |
| `agent` | `claude` \| `opencode` \| `manual` (source taxonomy) |
| `session_agent` | source-internal agent variant (e.g. OpenCode `build`/`plan`), nullable |
| `model` | model id (e.g. `big-pickle`, `claude-sonnet-4-6`) |
| `provider` | provider id (e.g. `opencode`, `anthropic`), nullable |
| `project` | opt-in label (basename or alias) — never the full path |
| `started_at`, `ended_at`, `duration_s` | session wall-clock window (end-to-end, not pure model time) |
| `turns` | assistant turns |
| `input_tokens` | everything sent to the model (prompts, context, tool results) |
| `output_tokens` | total model output |
| `junk_tokens` | aborted/interrupted generations only; `null` when not captured |
| `genuine_output_tokens` | `output - junk` when junk captured, else `output` |
| `reasoning_tokens` | reasoning/thinking tokens, nullable |
| `cache_read_tokens`, `cache_write_tokens` | nullable |
| `chars_in`, `chars_out`, `chars_junk` | exact local char counts, nullable |
| `basis` | `provider` (counts from the source) \| `estimated` (chars ÷ constant) |
| `cost_usd` | provider-reported cost when available, nullable |
| `claudia_version` | producer version |
| `hash` | sha256 of the canonical row |

### Counting methodology

- **Provider basis** — use the source's own token counts when present
  (OpenCode `session` table; Claude `usage` block). Store `basis: provider`.
- **Estimated basis** — when the source reports no counts, count characters
  of message content locally and convert with `CHARS_PER_TOKEN = 4.0` (a
  documented constant, ~English BPE average). Store both the estimate and the
  exact `chars_*`, with `basis: estimated`. Where provider counts and char
  counts coexist, consumers can measure real tokens/char per model and
  calibrate the constant over time.
- **Junk = aborted only.** `thinking`/`tool_use` blocks are real output and
  count toward `output_tokens` (their char counts are still recorded for
  post-processors). Aborted generations are detected in Claude transcripts via
  interrupt markers (`isInterrupted`, `stop_reason: interrupted`); OpenCode
  does not track aborts, so its rows carry `junk_tokens: null` and
  `genuine_output_tokens == output_tokens`.
- **No model calls anywhere in the path.** Counting is purely local.

### Capture model

Post-hoc and out-of-band: `claudia index` reads already-written transcripts
and appends new rows, deduped by `session_id`. Nothing hooks into the
interactive session. `--install-cron` also schedules `index`; a container
entrypoint or the developer can run it on demand.

### Agent-agnosticism

Two readers normalize into one record type:
- `read_claude_sessions()` — Claude Code JSONL (content-based, plus `usage`
  when present).
- `read_opencode_sessions()` — read-only SQLite query of `opencode.db`
  (`CLAUDIA_OPENCODE_DB` override). Degrades gracefully on lock/schema
  errors.

## Consequences

- `claudia index` produces a small, machine-readable, shareable ledger —
  counts and timestamps only, never prompt text, file contents, or keys —
  satisfying the "public citations only" rule of bigtokentask consumers.
- The ledger is the cross-repo contract: claudia produces
  `xpal-coder-index/v1`; bigtokentask ingests it (ADR-0016).
- Session wall-clock `duration_s` is an upper bound on model time, not pure
  decode/prefill time; bigtokentask uses `output_tokens / duration_s` as an
  end-to-end throughput proxy, clearly labeled.
- `junk_tokens` for OpenCode is unknown (`null`), so genuine-vs-junk ratio
  comparisons across agents must treat missing junk conservatively.
- The existing summary gains a content-based fallback so it no longer reports
  "No usage data" when provider detail is absent.
- claudia stays stdlib-only and single-file (sqlite3 is stdlib).
