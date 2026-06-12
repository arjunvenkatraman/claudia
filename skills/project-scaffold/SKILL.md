---
name: project-scaffold
description: Scaffold the standard /xpal-src project structure — CLAUDE.md, docs/decisions ADRs, and tasks/ (todo.md + lessons.md). Use when initializing a new project under /xpal-src, when adding the standard structure to an existing project, or when adding a new ADR following the ADR-NNN-kebab-title convention.
---

# Project scaffold (/xpal-src convention)

Creates the conventional project layout used across the `/xpal-src` workspace (as seen in `claudia`, `swarashruti`, `eka-bodhi`):

```
<project>/
├── CLAUDE.md           # development guidelines / project guide
├── docs/decisions/     # ADRs — ADR-NNN-kebab-title.md
├── tasks/
│   ├── todo.md         # Shipped / Upcoming / Known issues
│   └── lessons.md      # dated discoveries and gotchas
└── tests/              # (code projects only)
```

## When to use
- Initialising a new project directory under `/xpal-src`.
- Adding the standard `CLAUDE.md` + `docs/decisions/` + `tasks/` structure to an existing project that lacks it.
- Adding the next-numbered ADR to an existing `docs/decisions/`.

## Fast path — the helper script
A stdlib-only Python helper sits next to this file. It never overwrites existing files.

```bash
# Initialise structure (use --code-project to also create tests/)
python3 scaffold.py /xpal-src/<project> --name <project> --summary "One-line description." [--code-project]

# Add the next ADR (auto-numbers ADR-NNN from existing files)
python3 scaffold.py /xpal-src/<project> --add-adr "kebab-title" --title "Human Readable Title"
```

Resolve the script path relative to this skill (e.g. `~/.claude/skills/project-scaffold/scaffold.py`).

## Manual templates
If creating files by hand, follow these.

### CLAUDE.md
```markdown
# <project> — development guidelines

## What this project is
<one-paragraph description>

## Repository layout
<tree of the project>

## Conventions
- Write an ADR for any non-obvious design or scope decision.
- Track work in tasks/todo.md; record gotchas in tasks/lessons.md.

## Git workflow
- Conventional commits: feat:, fix:, docs:, chore:.
- Do not commit secrets.
```

### ADR (`docs/decisions/ADR-NNN-kebab-title.md`)
Number is zero-padded and sequential (ADR-001, ADR-002, …). Sections in this exact order:
```markdown
# ADR-NNN: <title>

**Status:** Proposed | Accepted | Superseded

## Context
<situation and forces>

## Decision
<what we decided>

## Consequences
<trade-offs and follow-ups>
```

### tasks/todo.md
Three sections: `## Shipped` (`[x]`), `## Upcoming` (`[ ]`), `## Known issues / watch items`.

### tasks/lessons.md
`# Lessons learned`, then dated blocks: `## YYYY-MM-DD — <heading>`.

## Notes
- Keep the helper script stdlib-only (matches the claudia project ethos — runs on system Python, no venv).
- For content/documentation projects, omit `--code-project` (no `tests/`).
