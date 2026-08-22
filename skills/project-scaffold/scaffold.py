#!/usr/bin/env python3
"""Scaffold the standard /xpal-src project structure (stdlib only).

Creates the conventional layout used across /xpal-src projects:
  <dir>/CLAUDE.md
  <dir>/docs/decisions/        (ADRs; with .gitkeep)
  <dir>/tasks/todo.md          (Shipped / Upcoming / Known issues)
  <dir>/tasks/lessons.md       (dated discoveries)
  <dir>/tests/                 (only with --code-project)

Also installs the `prepare-commit-msg` git hook (skills/project-scaffold/
prepare-commit-msg.sh) so every commit carries `Coding-Agent:` and `Model:`
trailers.

Never overwrites existing files — it skips them and reports.

Usage:
  scaffold.py <dir> --name NAME --summary "one-line summary" [--code-project]
  scaffold.py <dir> --add-adr "kebab-title" [--title "Human Readable Title"]
  scaffold.py <dir> --install-git-hook
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path

CLAUDE_MD = """# {name} — development guidelines

## What this project is
{summary}

## Repository layout
```
{name}/
├── CLAUDE.md           # this file
├── docs/decisions/     # ADRs — read before changing core approach
├── tasks/
│   ├── todo.md         # Shipped / Upcoming / Known issues
│   └── lessons.md      # dated discoveries and gotchas
{tests_line}```

## Conventions
- Write an ADR in `docs/decisions/` for any non-obvious design or scope decision
  (format: Status / Context / Decision / Consequences; numbered `ADR-NNN-kebab-title.md`).
- Track work in `tasks/todo.md`; record gotchas in `tasks/lessons.md`.

## Git workflow
- Conventional commits: `feat:`, `fix:`, `docs:`, `chore:`.
- Every commit carries `Coding-Agent:` (`claude`, `opencode`, or `manual`) and
  `Model:` trailers, appended by the `prepare-commit-msg` hook installed by
  the scaffold (`Model:` needs `claudia` on `PATH`; falls back to `unknown`
  otherwise). Reinstall with: `python3 <skill>/scaffold.py <dir> --install-git-hook`.
- Do not commit secrets (API keys, tokens).
"""

TODO_MD = """# {name} — tasks

## Shipped
- [x] Project scaffolding: CLAUDE.md, docs/decisions, tasks/

## Upcoming
- [ ] <first task>

## Known issues / watch items
- <none yet>
"""

LESSONS_MD = """# Lessons learned

## {date} — Project initialised
- Scaffolded with the project-scaffold skill.
"""

ADR_MD = """# ADR-{num}: {title}

**Status:** Proposed

## Context

<What is the situation and the forces at play? What problem are we solving?>

## Decision

<What did we decide to do?>

## Consequences

<What becomes easier or harder as a result? Trade-offs, follow-ups.>
"""


def kebab(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower())
    return s.strip("-")


def write_if_absent(path: Path, content: str, created: list, skipped: list) -> None:
    if path.exists():
        skipped.append(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    created.append(path)


def next_adr_number(decisions: Path) -> str:
    nums = []
    for p in decisions.glob("ADR-*.md"):
        m = re.match(r"ADR-(\d+)", p.name)
        if m:
            nums.append(int(m.group(1)))
    return f"{(max(nums) + 1) if nums else 1:03d}"


def git_hooks_dir(root: Path) -> Path:
    """Resolve the git hooks directory, honoring core.hooksPath when set."""
    try:
        r = subprocess.run(["git", "-C", str(root), "config", "--get", "core.hooksPath"],
                           capture_output=True, text=True)
        p = r.stdout.strip()
        if p:
            hp = Path(p)
            return hp if hp.is_absolute() else root / hp
    except OSError:
        pass
    return root / ".git" / "hooks"


def install_git_hook(root: Path) -> int:
    """Install the Coding-Agent prepare-commit-msg hook into the repo."""
    hook_src = Path(__file__).parent / "prepare-commit-msg.sh"
    if not hook_src.exists():
        print(f"missing hook template next to this script: {hook_src}", file=sys.stderr)
        return 1
    hooks_dir = git_hooks_dir(root)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    dest = hooks_dir / "prepare-commit-msg"
    if dest.exists():
        print(f"exists, skipped: {dest}")
        return 0
    dest.write_text(hook_src.read_text(encoding="utf-8"), encoding="utf-8")
    dest.chmod(dest.stat().st_mode | 0o755)
    print(f"created: {dest}")
    return 0


def add_adr(root: Path, kebab_title: str, title: str | None) -> int:
    decisions = root / "docs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    num = next_adr_number(decisions)
    slug = kebab(kebab_title)
    human = title or kebab_title.replace("-", " ").strip().capitalize()
    path = decisions / f"ADR-{num}-{slug}.md"
    if path.exists():
        print(f"exists, skipped: {path}")
        return 1
    path.write_text(ADR_MD.format(num=num, title=human), encoding="utf-8")
    print(f"created: {path}")
    return 0


def init(root: Path, name: str, summary: str, code_project: bool) -> int:
    created: list = []
    skipped: list = []
    tests_line = "└── tests/              # unit tests\n" if code_project else ""
    write_if_absent(root / "CLAUDE.md",
                    CLAUDE_MD.format(name=name, summary=summary, tests_line=tests_line),
                    created, skipped)
    write_if_absent(root / "docs" / "decisions" / ".gitkeep", "", created, skipped)
    write_if_absent(root / "tasks" / "todo.md", TODO_MD.format(name=name), created, skipped)
    write_if_absent(root / "tasks" / "lessons.md",
                    LESSONS_MD.format(date=_dt.date.today().isoformat()), created, skipped)
    if code_project:
        write_if_absent(root / "tests" / ".gitkeep", "", created, skipped)
    for p in created:
        print(f"created: {p}")
    for p in skipped:
        print(f"exists, skipped: {p}")
    install_git_hook(root)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold the standard /xpal-src project structure.")
    ap.add_argument("dir", help="target project directory")
    ap.add_argument("--name", help="project name (defaults to dir basename)")
    ap.add_argument("--summary", default="<one-line description of what this project is>")
    ap.add_argument("--code-project", action="store_true", help="also create tests/")
    ap.add_argument("--add-adr", metavar="KEBAB_TITLE", help="add the next-numbered ADR instead of init")
    ap.add_argument("--title", help="human-readable ADR title (with --add-adr)")
    ap.add_argument("--install-git-hook", action="store_true",
                    help="install the Coding-Agent prepare-commit-msg hook (existing projects)")
    args = ap.parse_args()

    root = Path(args.dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.add_adr:
        return add_adr(root, args.add_adr, args.title)
    if args.install_git_hook:
        return install_git_hook(root)
    name = args.name or root.name
    return init(root, name, args.summary, args.code_project)


if __name__ == "__main__":
    raise SystemExit(main())
