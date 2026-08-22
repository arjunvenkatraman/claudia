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

## How work is tracked here

Three layers, each with a distinct job:

1. **GitHub issues** — one issue per *discrete, closable* piece of work (a bug,
   a feature, a single phase step). Issues can be assigned, closed, referenced
   from commits, and grouped.
2. **Milestones** — group issues into a *time-boxed or phased* effort (e.g.
   "Rollout — personal tracking (Phases A+B)"). Milestones carry a due date and
   progress; an issue belongs to at most one milestone.
3. **tasks/todo.md** — the local canonical *log* of shipped/upcoming/known
   work, carrying ADR + issue links. The tracker is GitHub; the record is
   todo.md.

When to use which:

- **Discrete deliverable** → file an issue.
- **Part of a phase** → file the issue *and* attach it to the matching
  milestone.
- **Time-boxed activity** (like a tracking week) → milestone + per-step
  issues, not one big issue.
- **Cross-repo or multi-machine phase** → a GitHub Project board pulling
  issues from all involved repos is the best single view; per-repo milestones
  plus one issue per step also works without one.

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
   the issue); attach it to the matching milestone when it is part of a phase
   (see "How work is tracked here").
3. **Todo entry** — add the task to `tasks/todo.md` with a link to the issue.
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

## ADR decision points and chat loops

**Hard rule:** All public reference claims must include a URL. No exceptions. If you cite a
report, article, dataset, or benchmark, the URL must be included. Unverifiable claims without
sources weaken the decision record and cannot be fact-checked by other contributors.

**Hard rule:** All file references (ADRs, docs, issues) must be hyperlinked with **absolute
URLs**. When referencing an ADR like `ADR-0005`, link it to the full GitHub URL
(e.g. `https://github.com/arjunvenkatraman/bigtokentask/blob/main/docs/decisions/ADR-0005-base-case-utilization.md`).
When referencing an issue, use the full GitHub issue URL. Relative paths don't render as
clickable links in GitHub issues — always use absolute URLs so readers can follow the chain
of reasoning.

When working on design decisions (ADRs), chat loops and coding agents should:

### During discussion
1. **Reference existing ADRs** — always check `docs/decisions/` before proposing new approaches
2. **Document evidence** — when research uncovers new data relevant to an ADR, file an issue with the evidence (see template below)
3. **Cross-reference issues** — link ADRs to GitHub issues and vice versa

### When evidence emerges
If during a chat loop you discover data that affects a Proposed ADR:

1. **File an issue** documenting the evidence with citations
2. **Comment on the ADR** referencing the new issue
3. **Update tasks/todo.md** with the finding

### Issue template for ADR evidence

```markdown
**ADR affected:** [ADR-XXX](https://github.com/<owner>/<repo>/blob/main/docs/decisions/ADR-XXX-kebab-title.md)
**Status:** Proposed / Accepted
**Evidence type:** [ ] Data [ ] Citation [ ] Benchmark [ ] Case study

**Finding**
<description of the evidence>

**Source**
<citation with absolute URL — REQUIRED for all public references>

**Related issues**
- [#[issue-number](https://github.com/<owner>/<repo>/issues/<number>) — <brief description>

**Implications**
<how this affects the ADR decision>

**Action items**
- [ ] Update ADR context section
- [ ] Revise decision options
- [ ] Run model/sensitivity analysis
- [ ] Update claims-register.md (if applicable)
```

### Chat loop workflow for ADR decisions

1. **Read** the ADR and related issues
2. **Research** — use web search, read sources, gather evidence
3. **Document** — file issues for new evidence, comment on ADRs
4. **Propose** — suggest updates to the ADR based on evidence
5. **Implement** — once decision is accepted, update model/data and tests
6. **Verify** — run tests, update claims-register.md, close related issues

This ensures multi-contributor reflection and that evidence-based decisions are traceable.
