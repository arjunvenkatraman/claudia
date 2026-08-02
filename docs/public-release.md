# Public release protocol

Before pushing this repository to any **public** location, run the cleanup
protocol below. It removes or catches strings that could identify the original
author or their machine. For a **private** repo this is optional — run
`--strict` only when preparing a public release.

## 1. Run the scanner

```bash
./scripts/scrub-public.sh            # report only
./scripts/scrub-public.sh --strict   # fail on review items too
```

Two tiers:

| Tier | Examples | Action |
|---|---|---|
| **CRITICAL** | real names/usernames, `sk-ant-*` / `ghp_` / `glpat-` tokens, `localhost:PORT`, `/Users/...`, tracked `.DS_Store`, `.env`, `.claude/` | must fix before any push — scanner exits 1 |
| **REVIEW** | the `xpal` internal prefix (image names, `/xpal-*` container paths, `XPAL_*` env vars) | fine for private repos; rename for public ones (`--strict` fails) |

## 2. Fix CRITICAL hits

- **Secret tokens**: remove from the file, or better, move to an untracked
  local file (`*.env` style). Never commit credentials.
- **Tracked local state**: `git rm --cached` the offending files and add them
  to `.gitignore`:
  ```bash
  git rm --cached .DS_Store .claude/settings.local.json
  ```
  `.claude/settings.local.json` holds per-machine settings (paths, ports,
  allow-rules) — it must never be shared. Keep it local.
- **Usernames / host paths**: rewrite to placeholders (`<you>`, `/Users/you/...`).

## 3. Rename the internal prefix for a public repo (REVIEW tier)

If you publish, the `xpal` naming should become neutral. Because it appears in
identifiers and paths, rename it consistently and commit the rename as one
revision:

```bash
# Dry run first:
./scripts/scrub-public.sh --strict | grep -E "xpal|XPAL"

# Then replace (example: xpal -> dev):
for pat in "xpal:dev" "XPAL:DEV" "xpal:dev"; do
  old="${pat%%:*}"; new="${pat##*:}"
  # apply only to tracked text files; skip the scanner and this doc
  git ls-files | grep -vE "^(scripts/scrub-public\.sh|docs/public-release\.md)$" \
    | xargs sed -i "s/$old/$new/g"
done
```

After renaming: rebuild the image (`./containerconf/build.sh`), re-run
`./containerconf/setup.sh` to regenerate `.env` with the new defaults, and run
the scanner again until it is clean.

## 4. Final checklist

- [ ] `./scripts/scrub-public.sh --strict` exits 0
- [ ] No `.DS_Store`, `.env`, or `.claude/` file is tracked
- [ ] `git remote -v` points at the **new** public repo (not a personal repo)
- [ ] `.git/config` has no personal credentials baked in
- [ ] No real names, usernames, or `localhost` ports remain in `git ls-files`
- [ ] `.env` is still present locally (never committed) and `.env.example`
      documents the shape without personal values
