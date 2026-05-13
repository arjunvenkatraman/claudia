# ADR-003: Use Anthropic Admin API for optional cross-verification

**Status:** Accepted

## Context

Local JSONL data is machine-local and uses an undocumented schema. Users on shared org
accounts want to cross-check their usage against Anthropic's authoritative records, and
to filter usage by their specific API key in a multi-user workspace.

## Decision

Add `--verify` as an optional command that calls the Anthropic Admin API and prints a
side-by-side comparison of API vs local totals.

**Endpoint:** `GET https://api.anthropic.com/v1/organizations/usage_report/messages`

**Auth:** Admin API key (`sk-ant-admin...`) passed via `ANTHROPIC_ADMIN_KEY` env var.
A regular user API key is insufficient — this endpoint requires org-admin access.

**Key parameters used:**
- `starting_at` / `ending_at` — derived from the date range of local data
- `bucket_width=1d` — daily granularity
- `group_by[]=model&group_by[]=api_key_id` — enables per-model, per-key breakdown
- `api_key_ids[]` — optional filter, passed via `--api-key-id` (repeatable flag)

**Pagination:** The response is cursor-paginated (`has_more` / `next_page`). The
implementation follows all pages before returning.

**Token field mapping** (API → local JSONL):

| API field | Local field |
|---|---|
| `uncached_input_tokens` | `input_tokens` |
| `output_tokens` | `output_tokens` |
| `cache_read_input_tokens` | `cache_read_input_tokens` |
| `cache_creation.ephemeral_1h_input_tokens` + `ephemeral_5m_input_tokens` | `cache_creation_input_tokens` |

## Consequences

- **Requires Admin access** — most individual contributors will need to ask their org admin
  for either an Admin key or their API key ID.
- **API tracks API-key usage** — if Claude Code sessions are running under a shared service
  key rather than a personal key, `--api-key-id` filtering may not isolate individual usage.
- **Not available on AWS deployments** — the Admin API usage endpoint is unavailable when
  Anthropic is accessed through AWS Marketplace.
- **Data freshness** — API usage data appears within ~5 minutes of request completion;
  local JSONL is written in real time.
- **Delta ≠ error** — a non-zero delta between API and local is expected if: (a) sessions
  were run on other machines, (b) the API key ID filter is not applied, or (c) the local
  JSONL files were cleared.
