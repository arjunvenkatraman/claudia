#!/usr/bin/env python3
"""Fixture-based tests for claudia.

Run with: python3 -m unittest tests/test_claudia.py
"""
import importlib.util
import json
import os
import pathlib
import sqlite3
import sys
import tempfile
import unittest

# Load claudia.py as a module from source tree
_SRC = pathlib.Path(__file__).parent.parent / "claudia.py"
_spec = importlib.util.spec_from_file_location("claudia", _SRC)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

calc_cost    = _mod.calc_cost
calc_env     = _mod.calc_env
aggregate    = _mod.aggregate
build_api_data = _mod.build_api_data
fmt_tok      = _mod.fmt_tok
PRICING      = _mod.PRICING
DEFAULT_PRICING = _mod.DEFAULT_PRICING

# ── sample entries (two sessions, two models) ─────────────────────────────────

ENTRIES = [
    {
        "ts": "2026-04-01T10:00:00Z", "date": "2026-04-01", "week": "2026-W14",
        "month": "2026-04", "project": "/proj/a", "session": "s1",
        "model": "claude-sonnet-4-6",
        "inp": 1000, "out": 500, "cw": 200, "cr": 800,
    },
    {
        "ts": "2026-04-02T10:00:00Z", "date": "2026-04-02", "week": "2026-W14",
        "month": "2026-04", "project": "/proj/a", "session": "s1",
        "model": "claude-sonnet-4-6",
        "inp": 2000, "out": 1000, "cw": 400, "cr": 1600,
    },
    {
        "ts": "2026-05-01T10:00:00Z", "date": "2026-05-01", "week": "2026-W18",
        "month": "2026-05", "project": "/proj/b", "session": "s2",
        "model": "claude-haiku-4-5-20251001",
        "inp": 500, "out": 200, "cw": 100, "cr": 400,
    },
]


class TestCalcCost(unittest.TestCase):
    def test_known_model(self):
        # sonnet: (3.00, 15.00, 3.75, 0.30) per million
        cost = calc_cost("claude-sonnet-4-6", 1_000_000, 1_000_000, 1_000_000, 1_000_000)
        self.assertAlmostEqual(cost, 3.00 + 15.00 + 3.75 + 0.30)

    def test_unknown_model_uses_default(self):
        cost_known   = calc_cost("claude-sonnet-4-6", 1000, 1000, 1000, 1000)
        cost_unknown = calc_cost("claude-unknown-99", 1000, 1000, 1000, 1000)
        self.assertAlmostEqual(cost_known, cost_unknown)

    def test_zero_tokens(self):
        self.assertEqual(calc_cost("claude-sonnet-4-6", 0, 0, 0, 0), 0.0)

    def test_haiku_cheaper_than_sonnet(self):
        cost_haiku  = calc_cost("claude-haiku-4-5-20251001", 1_000_000, 1_000_000, 0, 0)
        cost_sonnet = calc_cost("claude-sonnet-4-6",         1_000_000, 1_000_000, 0, 0)
        self.assertLess(cost_haiku, cost_sonnet)


class TestCalcEnv(unittest.TestCase):
    def test_returns_three_values(self):
        result = calc_env(1000, 1000, 1000, 1000)
        self.assertEqual(len(result), 3)

    def test_zero_tokens(self):
        kwh, water, carbon = calc_env(0, 0, 0, 0)
        self.assertEqual(kwh, 0.0)
        self.assertEqual(water, 0.0)
        self.assertEqual(carbon, 0.0)

    def test_output_dominates_energy(self):
        # output tokens (0.39 J) cost more energy than cache reads (0.02 J)
        _, _, carbon_out = calc_env(0, 1_000_000, 0, 0)
        _, _, carbon_cr  = calc_env(0, 0, 0, 1_000_000)
        self.assertGreater(carbon_out, carbon_cr)

    def test_water_proportional_to_energy(self):
        kwh, water, _ = calc_env(1000, 1000, 1000, 1000)
        self.assertAlmostEqual(water / kwh, _mod.WUE_L_PER_KWH, places=5)


class TestAggregate(unittest.TestCase):
    def test_by_project(self):
        buckets = aggregate(ENTRIES, "project")
        self.assertIn("/proj/a", buckets)
        self.assertIn("/proj/b", buckets)
        self.assertEqual(buckets["/proj/a"]["turns"], 2)
        self.assertEqual(buckets["/proj/b"]["turns"], 1)

    def test_by_month(self):
        buckets = aggregate(ENTRIES, "month")
        self.assertIn("2026-04", buckets)
        self.assertIn("2026-05", buckets)
        self.assertEqual(buckets["2026-04"]["turns"], 2)

    def test_token_sums(self):
        buckets = aggregate(ENTRIES, "project")
        a = buckets["/proj/a"]
        self.assertEqual(a["inp"], 3000)
        self.assertEqual(a["out"], 1500)
        self.assertEqual(a["cw"],   600)
        self.assertEqual(a["cr"],  2400)

    def test_session_dedup(self):
        buckets = aggregate(ENTRIES, "project")
        # Both /proj/a entries share session s1
        self.assertEqual(len(buckets["/proj/a"]["sessions"]), 1)

    def test_cost_positive(self):
        buckets = aggregate(ENTRIES, "project")
        self.assertGreater(buckets["/proj/a"]["cost"], 0)
        self.assertGreater(buckets["/proj/b"]["cost"], 0)


class TestBuildApiData(unittest.TestCase):
    def setUp(self):
        self.data = build_api_data(ENTRIES)

    def test_structure(self):
        for key in ("generated_at", "summary", "by_project", "by_month", "by_model"):
            self.assertIn(key, self.data)

    def test_summary_fields(self):
        s = self.data["summary"]
        for field in ("period_start", "period_end", "turns", "sessions",
                      "cost", "inp", "out", "cw", "cr",
                      "energy_kwh", "water_l", "carbon_kg"):
            self.assertIn(field, s)

    def test_summary_totals(self):
        s = self.data["summary"]
        self.assertEqual(s["turns"], 3)
        self.assertEqual(s["inp"], 3500)
        self.assertEqual(s["out"], 1700)

    def test_by_project_sorted_by_cost(self):
        proj = self.data["by_project"]
        costs = [p["cost"] for p in proj]
        self.assertEqual(costs, sorted(costs, reverse=True))

    def test_by_month_sorted_chronologically(self):
        months = [m["label"] for m in self.data["by_month"]]
        self.assertEqual(months, sorted(months))

    def test_empty_entries(self):
        result = build_api_data([])
        self.assertIn("error", result)


class TestFmtTok(unittest.TestCase):
    def test_millions(self):
        self.assertEqual(fmt_tok(2_500_000), "2.50M")

    def test_thousands(self):
        self.assertEqual(fmt_tok(1_500), "1.5K")

    def test_small(self):
        self.assertEqual(fmt_tok(42), "42")


class TestLoadEntriesFromFixture(unittest.TestCase):
    """Integration test: write a real JSONL file and load it."""

    FIXTURE = json.dumps({
        "type": "assistant",
        "timestamp": "2026-06-01T12:00:00Z",
        "sessionId": "abc123",
        "cwd": "/projects/test",
        "message": {
            "model": "claude-sonnet-4-6",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 200,
                "cache_creation_input_tokens": 50,
                "cache_read_input_tokens": 300,
            },
        },
    })

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = pathlib.Path(tmpdir) / ".claude" / "projects" / "test-proj"
            proj_dir.mkdir(parents=True)
            (proj_dir / "session.jsonl").write_text(self.FIXTURE + "\n")

            orig_home = pathlib.Path.home
            try:
                pathlib.Path.home = staticmethod(lambda: pathlib.Path(tmpdir))
                entries = _mod.load_entries()
            finally:
                pathlib.Path.home = staticmethod(orig_home)

        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["inp"],  100)
        self.assertEqual(e["out"],  200)
        self.assertEqual(e["cw"],    50)
        self.assertEqual(e["cr"],   300)
        self.assertEqual(e["model"], "claude-sonnet-4-6")
        self.assertEqual(e["project"], "/projects/test")


class TestLoadEntriesModelFilter(unittest.TestCase):
    """Verify that model_filter restricts entries to matching models."""

    def _write_fixture(self, tmpdir, model):
        proj_dir = pathlib.Path(tmpdir) / ".claude" / "projects" / "test-proj"
        proj_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "type": "assistant",
            "timestamp": "2026-06-01T12:00:00Z",
            "sessionId": "abc",
            "cwd": "/projects/test",
            "message": {
                "model": model,
                "usage": {"input_tokens": 10, "output_tokens": 5,
                          "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
            },
        })
        (proj_dir / "session.jsonl").write_text(line + "\n")

    def _load(self, tmpdir, **kwargs):
        orig_home = pathlib.Path.home
        try:
            pathlib.Path.home = staticmethod(lambda: pathlib.Path(tmpdir))
            return _mod.load_entries(**kwargs)
        finally:
            pathlib.Path.home = staticmethod(orig_home)

    def test_no_filter_returns_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_fixture(tmpdir, "claude-sonnet-4-6")
            self.assertEqual(len(self._load(tmpdir)), 1)

    def test_matching_filter_returns_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_fixture(tmpdir, "claude-sonnet-4-6")
            entries = self._load(tmpdir, model_filter="sonnet")
            self.assertEqual(len(entries), 1)
            self.assertIn("sonnet", entries[0]["model"])

    def test_non_matching_filter_excludes_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_fixture(tmpdir, "claude-sonnet-4-6")
            entries = self._load(tmpdir, model_filter="opus")
            self.assertEqual(len(entries), 0)

    def test_exact_match_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_fixture(tmpdir, "claude-haiku-4-5-20251001")
            entries = self._load(tmpdir, model_filter="haiku")
            self.assertEqual(len(entries), 1)


class TestGitHook(unittest.TestCase):
    """The Coding-Agent prepare-commit-msg hook: embedded copy stays in sync
    with the canonical file in the project-scaffold skill."""

    CANONICAL = pathlib.Path(__file__).parent.parent / "skills" / "project-scaffold" / "prepare-commit-msg.sh"

    def test_embedded_hook_present(self):
        hook = _mod.GIT_HOOK_PREPARE_COMMIT_MSG
        self.assertIn("Coding-Agent", hook)
        self.assertIn("CLAUDE_CODE_ENTRYPOINT", hook)
        self.assertIn("OPENCODE", hook)
        self.assertIn("manual", hook)

    def test_embedded_hook_matches_canonical_file(self):
        canonical = self.CANONICAL.read_text(encoding="utf-8")
        self.assertEqual(
            _mod.GIT_HOOK_PREPARE_COMMIT_MSG,
            canonical,
            "claudia.py GIT_HOOK_PREPARE_COMMIT_MSG drifted from "
            "skills/project-scaffold/prepare-commit-msg.sh",
        )

    def test_install_git_hook_writes_executable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir) / "repo"
            _mod.cmd_install_git_hook(str(repo))
            hook = repo / ".git" / "hooks" / "prepare-commit-msg"
            self.assertTrue(hook.exists())
            self.assertTrue(hook.stat().st_mode & 0o111, "hook must be executable")
            self.assertEqual(hook.read_text(encoding="utf-8"),
                             self.CANONICAL.read_text(encoding="utf-8"))

    def test_install_git_hook_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir) / "repo"
            _mod.cmd_install_git_hook(str(repo))
            hook = repo / ".git" / "hooks" / "prepare-commit-msg"
            first_mtime = hook.stat().st_mtime_ns
            _mod.cmd_install_git_hook(str(repo))
            self.assertEqual(hook.stat().st_mtime_ns, first_mtime,
                             "re-install must not overwrite an existing hook")


# ── coder session index (ADR-006) ─────────────────────────────────────────────

def _write_claude_fixture(tmpdir, lines):
    pdir = pathlib.Path(tmpdir) / ".claude" / "projects" / "demo"
    pdir.mkdir(parents=True)
    (pdir / "s.jsonl").write_text("".join(json.dumps(l) + "\n" for l in lines))


def _with_home(tmpdir, fn):
    orig_home = pathlib.Path.home
    try:
        pathlib.Path.home = staticmethod(lambda: pathlib.Path(tmpdir))
        return fn()
    finally:
        pathlib.Path.home = staticmethod(orig_home)


def _make_opencode_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute("""CREATE TABLE session (
        id TEXT, agent TEXT, model TEXT, tokens_input INTEGER, tokens_output INTEGER,
        tokens_reasoning INTEGER, tokens_cache_read INTEGER, tokens_cache_write INTEGER,
        cost REAL, time_created INTEGER, time_updated INTEGER, title TEXT, directory TEXT,
        time_archived INTEGER)""")
    conn.execute("CREATE TABLE part (session_id TEXT, data TEXT)")
    conn.execute("CREATE TABLE message (session_id TEXT, data TEXT)")
    conn.execute(
        "INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)",
        ("ses_aaa", "build", json.dumps({"id": "big-pickle", "providerID": "opencode"}),
         1000, 500, 200, 3000, 4000, 1.25, 1785600000000, 1785603600000, "t", "/proj/z"))
    conn.execute("INSERT INTO message VALUES ('ses_aaa', ?)", (json.dumps({"role": "assistant"}),))
    conn.execute("INSERT INTO message VALUES ('ses_aaa', ?)", (json.dumps({"role": "user"}),))
    conn.execute("INSERT INTO part VALUES ('ses_aaa', ?)",
                 (json.dumps({"type": "text", "text": "hello world"}),))
    conn.commit()
    conn.close()


class TestReadClaudeSessions(unittest.TestCase):
    def test_provider_basis_when_usage_present(self):
        with tempfile.TemporaryDirectory() as td:
            _write_claude_fixture(td, [{
                "type": "assistant", "sessionId": "s1", "timestamp": "2026-07-01T10:00:00Z",
                "cwd": "/proj/a",
                "message": {
                    "model": "claude-sonnet-4-6",
                    "usage": {"input_tokens": 100, "output_tokens": 50,
                              "cache_creation_input_tokens": 10, "cache_read_input_tokens": 20},
                    "content": [{"type": "text", "text": "hi"}],
                },
            }])
            recs = _with_home(td, lambda: _mod.read_claude_sessions())
            self.assertEqual(len(recs), 1)
            r = recs[0]
            self.assertEqual(r["basis"], "provider")
            self.assertEqual(r["input_tokens"], 100)
            self.assertEqual(r["output_tokens"], 50)
            self.assertEqual(r["junk_tokens"], 0)
            self.assertEqual(r["provider_usage"],
                             {"input": 100, "output": 50, "cache_read": 20, "cache_write": 10})

    def test_estimated_basis_and_junk_when_usage_absent(self):
        with tempfile.TemporaryDirectory() as td:
            _write_claude_fixture(td, [
                {"type": "user", "sessionId": "s2", "timestamp": "2026-07-01T10:00:00Z",
                 "cwd": "/proj/b", "message": {"content": "abcd"}},
                {"type": "assistant", "sessionId": "s2", "timestamp": "2026-07-01T10:00:01Z",
                 "cwd": "/proj/b", "message": {
                     "model": "claude-sonnet-4-6",
                     "content": [{"type": "text", "text": "x" * 80}]}},
                {"type": "assistant", "sessionId": "s2", "timestamp": "2026-07-01T10:00:02Z",
                 "cwd": "/proj/b", "message": {
                     "model": "claude-sonnet-4-6", "isInterrupted": True,
                     "stop_reason": "interrupted",
                     "content": [{"type": "text", "text": "y" * 40}]}},
            ])
            recs = _with_home(td, lambda: _mod.read_claude_sessions())
            self.assertEqual(len(recs), 1)
            r = recs[0]
            self.assertEqual(r["basis"], "estimated")
            self.assertEqual(r["input_tokens"], 1)     # 4 user chars / 4.0
            self.assertEqual(r["output_tokens"], 30)   # (80 + 40) / 4.0
            self.assertEqual(r["junk_tokens"], 10)     # interrupted 40 chars
            self.assertEqual(r["genuine_output_tokens"], 20)
            self.assertEqual(r["agent"], "claude")
            self.assertEqual(r["turns"], 2)
            self.assertIsNone(r["provider_usage"])
            self.assertEqual(r["schema"], "xpal-coder-index/v1")
            self.assertTrue(r["hash"])

    def test_synthetic_messages_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            _write_claude_fixture(td, [{
                "type": "assistant", "sessionId": "s3", "timestamp": "2026-07-01T10:00:00Z",
                "cwd": "/proj/c",
                "message": {"model": "<synthetic>",
                            "content": [{"type": "text", "text": "ignored"}]},
            }])
            self.assertEqual(_with_home(td, lambda: _mod.read_claude_sessions()), [])


class TestReadOpencodeSessions(unittest.TestCase):
    """Direct-SQLite fallback path (`_opencode_sessions_sqlite`) — used when no
    opencode CLI is available."""

    def _read_sqlite(self, td):
        db = pathlib.Path(td) / "opencode.db"
        _make_opencode_db(db)
        old = os.environ.get("CLAUDIA_OPENCODE_DB")
        os.environ["CLAUDIA_OPENCODE_DB"] = str(db)
        try:
            return _mod._opencode_sessions_sqlite()
        finally:
            if old is None:
                os.environ.pop("CLAUDIA_OPENCODE_DB", None)
            else:
                os.environ["CLAUDIA_OPENCODE_DB"] = old

    def test_reads_provider_rows(self):
        with tempfile.TemporaryDirectory() as td:
            recs = self._read_sqlite(td)
            self.assertEqual(len(recs), 1)
            r = recs[0]
            self.assertEqual(r["agent"], "opencode")
            self.assertEqual(r["session_agent"], "build")
            self.assertEqual(r["model"], "big-pickle")
            self.assertEqual(r["provider"], "opencode")
            self.assertEqual(r["basis"], "provider")
            self.assertEqual(r["input_tokens"], 1000)
            self.assertEqual(r["output_tokens"], 500)
            self.assertEqual(r["turns"], 1)
            self.assertIsNone(r["junk_tokens"])
            self.assertEqual(r["genuine_output_tokens"], 500)
            self.assertEqual(r["chars_out"], 11)   # "hello world"
            self.assertEqual(r["duration_s"], 3600.0)

    def test_missing_db_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            old_db  = os.environ.get("CLAUDIA_OPENCODE_DB")
            old_bin = os.environ.get("CLAUDIA_OPENCODE_BIN")
            os.environ["CLAUDIA_OPENCODE_DB"] = str(pathlib.Path(td) / "nope.db")
            os.environ["CLAUDIA_OPENCODE_BIN"] = str(pathlib.Path(td) / "no-opencode-cli")
            try:
                self.assertEqual(_mod.read_opencode_sessions(), [])
            finally:
                if old_db is None:
                    os.environ.pop("CLAUDIA_OPENCODE_DB", None)
                else:
                    os.environ["CLAUDIA_OPENCODE_DB"] = old_db
                if old_bin is None:
                    os.environ.pop("CLAUDIA_OPENCODE_BIN", None)
                else:
                    os.environ["CLAUDIA_OPENCODE_BIN"] = old_bin


def _write_opencode_stub(path, export):
    """A fake `opencode` CLI: `db` lists one session, `export <id>` dumps it."""
    stub = (
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "EXPORT = " + json.dumps(export) + "\n"
        "if sys.argv[1] == 'db':\n"
        "    print(json.dumps([{'id': EXPORT['info']['id']}]))\n"
        "elif sys.argv[1] == 'export':\n"
        "    print('Exporting session: ' + sys.argv[2])\n"
        "    print(json.dumps(EXPORT))\n"
    )
    path.write_text(stub)
    path.chmod(path.stat().st_mode | 0o111)


class TestOpencodeReportingTools(unittest.TestCase):
    """opencoide stats via its own reporting tools: `opencode db` + `opencode export`."""

    EXPORT = {
        "info": {
            "id": "ses_stub", "agent": "plan", "title": "stub",
            "directory": "/proj/z", "cost": 0.5,
            "model": {"id": "big-pickle", "providerID": "opencode"},
            "time": {"created": 1785600000000, "updated": 1785603600000},
            "tokens": {"input": 1000, "output": 500, "reasoning": 200,
                       "cache": {"read": 3000, "write": 4000}},
        },
        "messages": [
            {"info": {"role": "assistant"},
             "parts": [{"type": "text", "text": "hello world"},
                       {"type": "reasoning", "text": "think"}]},
            {"info": {"role": "user"}, "parts": []},
        ],
    }

    def test_reporting_tools_source(self):
        with tempfile.TemporaryDirectory() as td:
            stub = pathlib.Path(td) / "opencode"
            _write_opencode_stub(stub, self.EXPORT)
            old = os.environ.get("CLAUDIA_OPENCODE_BIN")
            os.environ["CLAUDIA_OPENCODE_BIN"] = str(stub)
            try:
                recs = _mod.read_opencode_sessions()
            finally:
                if old is None:
                    os.environ.pop("CLAUDIA_OPENCODE_BIN", None)
                else:
                    os.environ["CLAUDIA_OPENCODE_BIN"] = old
            self.assertEqual(len(recs), 1)
            r = recs[0]
            self.assertEqual(r["agent"], "opencode")
            self.assertEqual(r["session_agent"], "plan")
            self.assertEqual(r["model"], "big-pickle")
            self.assertEqual(r["provider"], "opencode")
            self.assertEqual(r["basis"], "provider")
            self.assertEqual(r["input_tokens"], 1000)
            self.assertEqual(r["output_tokens"], 500)
            self.assertEqual(r["reasoning_tokens"], 200)
            self.assertEqual(r["turns"], 1)
            self.assertIsNone(r["junk_tokens"])
            self.assertEqual(r["chars_out"], 16)   # "hello world" (11) + "think" (5)
            self.assertEqual(r["cost_usd"], 0.5)
            self.assertEqual(r["duration_s"], 3600.0)

    def test_broken_cli_falls_back_to_sqlite(self):
        with tempfile.TemporaryDirectory() as td:
            db  = pathlib.Path(td) / "opencode.db"
            _make_opencode_db(db)
            old_db  = os.environ.get("CLAUDIA_OPENCODE_DB")
            old_bin = os.environ.get("CLAUDIA_OPENCODE_BIN")
            os.environ["CLAUDIA_OPENCODE_DB"] = str(db)
            os.environ["CLAUDIA_OPENCODE_BIN"] = str(pathlib.Path(td) / "no-opencode-cli")
            try:
                recs = _mod.read_opencode_sessions()
            finally:
                if old_db is None:
                    os.environ.pop("CLAUDIA_OPENCODE_DB", None)
                else:
                    os.environ["CLAUDIA_OPENCODE_DB"] = old_db
                if old_bin is None:
                    os.environ.pop("CLAUDIA_OPENCODE_BIN", None)
                else:
                    os.environ["CLAUDIA_OPENCODE_BIN"] = old_bin
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["session_agent"], "build")  # from the fixture DB


class TestCmdIndex(unittest.TestCase):
    def test_append_dedup_export(self):
        with tempfile.TemporaryDirectory() as td:
            db  = pathlib.Path(td) / "opencode.db"
            _make_opencode_db(db)
            idx = pathlib.Path(td) / "ledger"
            out = pathlib.Path(td) / "exp"
            old_db  = os.environ.get("CLAUDIA_OPENCODE_DB")
            old_idx = os.environ.get("CLAUDIA_INDEX_DIR")
            old_bin = os.environ.get("CLAUDIA_OPENCODE_BIN")
            os.environ["CLAUDIA_OPENCODE_DB"]  = str(db)
            os.environ["CLAUDIA_INDEX_DIR"]   = str(idx)
            os.environ["CLAUDIA_OPENCODE_BIN"] = str(pathlib.Path(td) / "no-opencode-cli")
            try:
                _mod.cmd_index()
                ledger = idx / "coder-index.jsonl"
                self.assertEqual(len(ledger.read_text().splitlines()), 1)
                _mod.cmd_index()  # dedup — no new rows
                self.assertEqual(len(ledger.read_text().splitlines()), 1)
                _mod.cmd_index(out_dir=str(out))
                self.assertTrue((out / "coder-index.jsonl").exists())
                import contextlib
                with contextlib.redirect_stdout(open(os.devnull, "w")):
                    _mod.cmd_index(to_json=True)  # smoke — no exception
            finally:
                if old_db is None:
                    os.environ.pop("CLAUDIA_OPENCODE_DB", None)
                else:
                    os.environ["CLAUDIA_OPENCODE_DB"] = old_db
                if old_idx is None:
                    os.environ.pop("CLAUDIA_INDEX_DIR", None)
                else:
                    os.environ["CLAUDIA_INDEX_DIR"] = old_idx
                if old_bin is None:
                    os.environ.pop("CLAUDIA_OPENCODE_BIN", None)
                else:
                    os.environ["CLAUDIA_OPENCODE_BIN"] = old_bin


class TestLoadEntriesFallback(unittest.TestCase):
    def test_estimated_entry_included_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            _write_claude_fixture(td, [{
                "type": "assistant", "sessionId": "s9", "timestamp": "2026-07-01T10:00:00Z",
                "cwd": "/proj/nu",
                "message": {"model": "claude-sonnet-4-6",
                            "content": [{"type": "text", "text": "z" * 40}]},
            }])
            entries = _with_home(td, lambda: _mod.load_entries())
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["basis"], "estimated")
            self.assertEqual(entries[0]["out"], 10)

    def test_provider_only_when_fallback_false(self):
        with tempfile.TemporaryDirectory() as td:
            _write_claude_fixture(td, [{
                "type": "assistant", "sessionId": "s9", "timestamp": "2026-07-01T10:00:00Z",
                "cwd": "/proj/nu",
                "message": {"model": "claude-sonnet-4-6",
                            "content": [{"type": "text", "text": "z" * 40}]},
            }])
            self.assertEqual(_with_home(td, lambda: _mod.load_entries(fallback=False)), [])

    def test_provider_entry_flagged_provider(self):
        with tempfile.TemporaryDirectory() as td:
            _write_claude_fixture(td, [{
                "type": "assistant", "sessionId": "s9", "timestamp": "2026-07-01T10:00:00Z",
                "cwd": "/proj/nu",
                "message": {"model": "claude-sonnet-4-6",
                            "usage": {"input_tokens": 1, "output_tokens": 2},
                            "content": [{"type": "text", "text": "hi"}]},
            }])
            entries = _with_home(td, lambda: _mod.load_entries())
            self.assertEqual(entries[0]["basis"], "provider")


if __name__ == "__main__":
    unittest.main()
