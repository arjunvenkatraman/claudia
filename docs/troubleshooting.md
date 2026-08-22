# Troubleshooting

Diagnostics grouped by area. When in doubt, run with more context first:

```bash
claudia --help                       # confirm the flags you expect exist
claudia --since 2020-01-01           # include everything
ls ~/.claude/projects/               # confirm session logs exist
podman ps -a                        # container: is it running?
git config --get core.hooksPath     # hook: custom hooks dir in play?
```

## CLI

### "No data" / empty summary, but I've used Claude Code

The CLI reads `~/.claude/projects/**/*.jsonl`. If those don't exist — or you
redirected logs (`CLAUDIA_CLAUDE_DIR`) — nothing matches. Check the path above,
and honor the env-var overrides (see [usage.md](usage.md#environment-variable-overrides)):

```bash
ls ~/.claude/projects/ 2>&1
CLAUDIA_CLAUDE_DIR=/path/to/logs claudia
```

Also note Claude Code may prune old session logs; a `claudia --snapshot` +
`--install-cron` setup keeps daily totals even after pruning.

### `--verify` returns a large delta or errors

`--verify` compares local totals against the Anthropic Admin API; small
differences are normal (timing/rounding, JSONL writes not yet flushed). Large or
persistent ones usually mean:

- **Missing Admin key / wrong key type** — needs `sk-ant-admin...`, not a
  user `sk-ant-...`. See [filing-issues.md](filing-issues.md#include-this-environment-information).
- **403 / not available** — orgs that got Anthropic API via a marketplace
  (e.g. AWS Bedrock) contract don't get Admin API billing data. Nothing to fix
  locally.
- **Local totals larger** — the JSONL includes sessions the Admin API hasn't
  ingested yet; re-run later.

### `--by task-type --classifier haiku` wants a key

The `haiku` classifier needs `ANTHROPIC_API_KEY` (a *user* key) because it
makes a real model call. Either export it or use the offline `rules` backend:

```bash
ANTHROPIC_API_KEY=sk-ant-... claudia --by task-type --classifier haiku --yes
claudia --by task-type                          # rules is the default
```

### `--serve` port busy

```bash
claudia --serve --port 9000
```

### `--install-cron` does nothing visible

It adds a crontab entry (`crontab -l` to inspect). If `crontab` is missing on
the host (e.g. some minimal containers), install cron or run `--snapshot`
manually via your own scheduler.

### Cache token numbers look enormous

Claude Code caches context aggressively; cache-read tokens are counted in the
totals by design (they're billable). Not a bug — see `--cost` for the
cache/output/input split.

## Container environment

### Permission errors on the mounted folders

The container's `coder` user must map to your host UID. Both run scripts set
`--userns=keep-id`; if that isn't in effect, re-create the container. Confirm
`.env` has the right UID:

```bash
grep XPAL_HOST_UID containerconf/.env   # should match id -u
./setup.sh                              # fix and recreate
```

`--userns=keep-id` works with rootless Podman; with plain Docker or on some
macOS setups you may instead need to pass `-u $(id -u):$(id -g)` to the run
command.

### Can't reach the container by IP

Expected under rootless Podman — it has no host-routable IP. Use the published
ports (`$XPAL_PORTS`) on `localhost`, and make sure the server inside binds to
`0.0.0.0` not `127.0.0.1`.

### Files missing in a SharePoint mount

The bind mount needs a *locally synced* folder — a OneDrive/SharePoint library
shown as online-only placeholders won't have real files. In the sync client,
set the library/folder to "Always keep on this device". If the library isn't
synced locally at all, a bind mount can't reach it (you'd need `rclone` inside
the container).

### Rebuilt the image but the container is unchanged

A container is pinned to the image it was created from. `./build.sh` offers to
recreate it; run that. Changes to ports/names also require recreate.

### Day-to-day container is gone or in the wrong state

```bash
$XPAL_RUNTIME start -ai $XPAL_CONTAINER    # start+attach if it exists
./run-daily.sh                             # recreates if it doesn't
```

### Hand-installed packages vanished

They were never in the image. Reinstall, or promote them into the Containerfile
and `./build.sh` — see [container-env.md](container-env.md#tracking-hand-installed-dependencies).

## Coding-Agent / Model hook

### Commits aren't getting a `Coding-Agent:` trailer

Check, in order:

```bash
ls -l .git/hooks/prepare-commit-msg      # exists? executable?
git config --get core.hooksPath          # if set, hook must be in THAT dir
claudia --install-git-hook               # installs only if missing — see below
git commit --amend --no-edit             # verify on the next commit
```

A trailer only appears on commits authored through that repo's git — commits
created entirely on GitHub's web UI never run your hook (expected).

### `Coding-Agent: manual` on commits I made with an agent

Detection keys off the agent's own env markers (`OPENCODE=1`,
`CLAUDECODE=1`). If your agent doesn't set them (or you committed through a
proxy/CI that clears env), the hook falls back to `manual`. It errs toward
accuracy — a missing tag beats a wrong one.

### `Model: unknown` on an agent-tagged commit

Check, in order:

```bash
command -v claudia                       # must be on PATH for the hook to shell out to it
claudia --current-model                  # run it directly — what does it print?
echo "$CLAUDE_CODE_SESSION_ID"           # claude: must be set
ls "$(claudia --current-model 2>&1)"     # opencode: confirm ~/.local/share/opencode/opencode.db exists
```

`unknown` (as opposed to `n/a`) means the agent was detected but its model
lookup came up empty — most often `claudia` isn't installed/on `PATH` in the
shell that ran `git commit`, or the session log/db hasn't been written yet
(very first message of a session). See
[ADR-007](decisions/ADR-007-agent-model-trailer.md).

### Duplicate trailers after `--amend`

Shouldn't happen — the hook dedupes. If you see two, your repo has a stale
pre-`ADR-005` hook.

### Reinstalling the hook to pick up a newer version (e.g. to get `Model:`)

`--install-git-hook` **skips if a hook file is already present** — it does
not overwrite. To upgrade a repo tagged before ADR-007 (agent trailer only,
no model), remove the old hook first:

```bash
rm .git/hooks/prepare-commit-msg
claudia --install-git-hook
```

## General

### `claudia` isn't on PATH after `uv tool install .`

`uv tool` installs into a tools dir; on some shells you must add it to PATH
(`~/.local/bin` typically). Or use the manual copy:

```bash
cp claudia.py /usr/local/bin/claudia
```

### `Python >=3.10 required`

The tool needs 3.10+; if the system Python is older (e.g. Debian 10), use the
container environment, which ships a uv-managed modern CPython as `python3`.

## Still stuck?

File an issue with the details in [filing-issues.md](filing-issues.md) — the
more environment info you include, the faster it gets diagnosed. Never paste
API keys or raw session logs into an issue.
