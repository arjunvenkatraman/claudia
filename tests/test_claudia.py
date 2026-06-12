#!/usr/bin/env python3
"""Fixture-based tests for claudia.

Run with: python3 -m unittest tests/test_claudia.py
"""
import importlib.util
import json
import pathlib
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
        self.assertAlmostEqual(water / kwh, _mod.WATER_L_PER_KWH, places=5)


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


if __name__ == "__main__":
    unittest.main()
