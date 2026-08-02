# Filing issues

Bugs, feature requests, and questions all go to the repo's GitHub Issues:

**https://github.com/arjunvenkatraman/claudia/issues**

## Before you file

1. **Read the docs** — [troubleshooting.md](troubleshooting.md) covers the most
   common problems (missing logs, `--verify` deltas, permission errors, hook
   not tagging, SharePoint mounts).
2. **Search existing issues** — yours may already be open or closed. Add a
   comment instead of a duplicate.
3. **Reproduce once on a clean state** — e.g. `claudia --since 2020-01-01` to
   rule out a stale snapshot cache.

## Include this environment information

| Field | Example |
|---|---|
| `claudia` version | `0.3.0` (`claudia --version` if present, else commit hash) |
| Python version | `python3 --version` |
| OS / host | macOS 14.5 / Ubuntu 24.04 / WSL2 |
| Container runtime (if container issue) | `podman --version` / `docker --version`, rootless or not |
| Git / hooks | `git --version`; `git config --get core.hooksPath` |
| Claude Code | `claude --version` |
| Command that failed | the exact command line (strip secrets) |

## What to paste — and what never to paste

**Do include:** the exact command, the full error text, and any redacted config
(e.g. `.env` with secrets blanked: `XPAL_HOST_UID=1000`, `XPAL_PORTS="..."`).

**Never paste:** API keys (`sk-ant-...`, `sk-ant-admin-...`), `~/.claude/.credentials.json`, git
credential tokens, raw session JSONL, or personal prompts. Session logs contain
the actual text of everything you and Claude said — redact before attaching, or
describe instead of pasting.

## Templates

### Bug

```markdown
**Command run**
```
claudia --by week --env
```

**Expected**
Weekly totals plus environmental impact.

**Actual**
```
Traceback ... (paste error, or describe)
```

**Environment**
- claudia version:
- Python:
- OS:
- (container runtime, git version, Claude Code version as applicable)

**Steps to reproduce**
1. ...
2. ...
```

### Feature request

```markdown
**What problem does this solve?**

**Proposed behavior**
`claudia --some-new-flag ...`

**Alternatives considered**
```

### Question

Open it with a clear title; tag with `question` if the label exists.

## After filing

- Issues from this repo are typically triaged into
  [tasks/todo.md](../tasks/todo.md). A fix lands as a conventional commit
  (`fix:`, `feat:`, `docs:`) on a feature branch, via pull request.
- Feature work that changes the data source, estimation methodology, or API
  integration first gets an ADR in `docs/decisions/` — see the contributor
  workflow below.

## Contributing / the workflow used here

This repo follows a lightweight process — useful when you submit a PR:

1. **ADR first** — for any non-obvious design choice, write a short
   Architecture Decision Record in `docs/decisions/ADR-XXX-<slug>.md` (see the
   existing ones for the format).
2. **Issue** — open the GitHub issue referencing the ADR (or the ADR references
   the issue).
3. **Todo entry** — add the task to `tasks/todo.md`.
4. **Branch + PR** — implement on a feature branch (`feat/...`, `fix/...`,
   `docs/...`), with conventional-commit messages (`feat:`, `fix:`, `docs:`,
   `chore:`). Every commit should carry a `Coding-Agent:` trailer (see
   [agent-tagging.md](agent-tagging.md)); install the hook with
   `claudia --install-git-hook` before committing.
5. **Merge via GitHub** — then the branch is deleted locally and on the remote.

### Repo conventions to respect in a PR

- `claudia.py` is **stdlib-only and single-file** — no new third-party deps,
  no splitting the file without an ADR.
- After changing `claudia.py`, copy it to `/usr/local/bin/claudia` so your
  installed binary matches (per `CLAUDE.md`).
- Run the test suite before pushing:
  ```bash
  python3 -m unittest tests.test_claudia
  ```
- Don't commit secrets; `.env` is gitignored on purpose.
