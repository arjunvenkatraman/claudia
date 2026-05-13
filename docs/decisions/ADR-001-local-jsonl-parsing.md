# ADR-001: Read local JSONL session files as the primary data source

**Status:** Accepted

## Context

Claude Code writes every session to `~/.claude/projects/<slug>/*.jsonl` in real time.
Each line is a JSON object. Assistant turns include a `message.usage` block containing:
- `input_tokens`
- `output_tokens`
- `cache_creation_input_tokens`
- `cache_read_input_tokens`

The alternative is to query the Anthropic Admin API (`/v1/organizations/usage_report/messages`),
which is authoritative but requires an Admin API key, org membership, and a network call.

## Decision

Use local JSONL as the **primary and default** data source. The Admin API is an optional
cross-check (`--verify`), not the baseline.

Key facts discovered during implementation:
- Each `assistant` entry in the JSONL has `type: "assistant"` and a fully populated
  `message.usage` object including cache breakdown and model name.
- Entries also carry `cwd` (project path), `sessionId`, `timestamp`, and `version`.
- Synthetic turns (`model: "<synthetic>"`) must be filtered out — they appear in some
  internal tool-use flows and carry no real usage.
- The JSONL glob is: `~/.claude/projects/**/*.jsonl`

## Consequences

- **No auth required** for the core commands — instant, offline, zero latency.
- **Machine-local** — only sessions run on this machine are visible.
- **Schema is unofficial** — Anthropic does not document this format. It may change
  across Claude Code versions. The `version` field on each entry can be used to detect
  schema drift. Current tested version: `2.1.x`.
- The `--verify` command exists specifically to cross-check local data against the
  authoritative API when needed.
