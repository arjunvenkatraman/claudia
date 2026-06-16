#!/usr/bin/env python3
"""claudia — Claude Introspective Analysis.

Reads ~/.claude/projects/**/*.jsonl to report token usage,
estimated cost, and environmental impact across all local sessions.
"""

import argparse
import csv
import glob
import http.server
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

# Pricing per million tokens (input, output, cache_write, cache_read)
PRICING = {
    "claude-opus-4-7":           (15.00, 75.00, 18.75, 1.50),
    "claude-sonnet-4-6":         ( 3.00, 15.00,  3.75, 0.30),
    "claude-haiku-4-5-20251001": ( 0.80,  4.00,  1.00, 0.08),
    "claude-haiku-4-5":          ( 0.80,  4.00,  1.00, 0.08),
}
DEFAULT_PRICING = (3.00, 15.00, 3.75, 0.30)  # sonnet as fallback

# Energy per token at the GPU in Joules (IT equipment energy only; PUE applied separately)
# Source: TokenPowerBench (arxiv 2512.03024) and Luccioni et al. 2023 (ACL) for
# decode/prefill values; Agrawal et al. 2024 (OSDI) for prefill vs. decode cost split.
# Reflects large-parameter (50B+) model inference on H100-class hardware. ±50% uncertainty.
ENERGY_J = {
    "out": 0.39,   # decode: 1 full forward pass per output token (compute-bound)
    "inp": 0.13,   # prefill: 1 forward pass amortized over full context
    "cw":  0.13,   # cache write: same compute as prefill; KV activations stored to HBM
    "cr":  0.02,   # cache read: KV retrieval only — memory-bandwidth-bound, no matmul
}
JOULES_PER_KWH    = 3_600_000

# Power Usage Effectiveness: total facility energy ÷ IT equipment energy.
# Google global avg 2023: 1.10 (Google ESG 2023); AWS est: ~1.15; industry avg: 1.58.
# Using 1.12 for hyperscaler-class infrastructure (Anthropic runs on AWS/GCP).
PUE = 1.12

# Water Usage Effectiveness: liters of cooling water evaporated per IT kWh consumed.
# This is physical water consumed (evaporated in cooling towers) — not pumping energy.
# Source: Li et al. 2023 ("Making AI Less Thirsty", arxiv 2304.03271).
# Provider range: 0.49 L/kWh (Microsoft) to 1.80 L/kWh (industry avg).
# Using industry average as conservative estimate given infrastructure uncertainty.
WUE_L_PER_KWH    = 1.8

CARBON_KG_PER_KWH = 0.384  # US grid average 2024 (EPA / Ember)

# Real-world energy analogs
LED_HOUSE_KW       = 0.072  # 8 × 9W LED bulbs — 800 sq ft, 2-room house
LED_HOURS_PER_DAY  = 5.0    # assumed daily lighting hours
MEAL_KWH           = 0.5    # 30 min on a 1 kW electric burner

# Real-world water volume analogs (volume comparison, not energy)
WATER_GLASS_L   = 0.250   # standard 8 oz / 250 mL drinking glass
WATER_SHOWER_L  = 65.0    # 8-minute shower at 8 L/min (US EPA WaterSense)


def calc_cost(model, inp, out, cw, cr):
    p = PRICING.get(model, DEFAULT_PRICING)
    return (inp * p[0] + out * p[1] + cw * p[2] + cr * p[3]) / 1_000_000


def calc_env(inp, out, cw, cr):
    """Return (kwh_it, water_l, carbon_kg) for given token counts.

    kwh_it    — IT equipment energy (GPU compute only)
    water_l   — cooling water evaporated at the data center (WUE × IT kWh)
    carbon_kg — grid emissions from total facility draw (IT × PUE × carbon factor)
    """
    joules_it = (inp * ENERGY_J["inp"] + out * ENERGY_J["out"] +
                 cw  * ENERGY_J["cw"]  + cr  * ENERGY_J["cr"])
    kwh_it    = joules_it / JOULES_PER_KWH
    water_l   = kwh_it * WUE_L_PER_KWH
    carbon_kg = kwh_it * PUE * CARBON_KG_PER_KWH
    return kwh_it, water_l, carbon_kg


def load_entries(since=None, project_filter=None, model_filter=None):
    entries = []
    pattern = str(pathlib.Path.home() / ".claude/projects/**/*.jsonl")
    for f in glob.glob(pattern, recursive=True):
        with open(f, errors="replace") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("type") != "assistant":
                    continue
                msg = e.get("message", {})
                if "usage" not in msg or msg.get("model") in (None, "<synthetic>"):
                    continue
                ts = e.get("timestamp", "")
                if since and ts < since:
                    continue
                cwd = e.get("cwd", "unknown")
                if project_filter and project_filter not in cwd:
                    continue
                model = msg.get("model", "unknown")
                if model_filter and model_filter not in model:
                    continue
                u = msg["usage"]
                entries.append({
                    "ts":      ts,
                    "date":    ts[:10],
                    "week":    _week(ts),
                    "month":   ts[:7],
                    "project": cwd,
                    "session": e.get("sessionId", ""),
                    "model":   model,
                    "inp":     u.get("input_tokens", 0),
                    "out":     u.get("output_tokens", 0),
                    "cw":      u.get("cache_creation_input_tokens", 0),
                    "cr":      u.get("cache_read_input_tokens", 0),
                })
    return sorted(entries, key=lambda x: x["ts"])


def _week(ts):
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    except Exception:
        return ts[:7]


def aggregate(entries, key):
    buckets = defaultdict(lambda: {
        "turns": 0, "inp": 0, "out": 0, "cw": 0, "cr": 0,
        "cost": 0.0, "energy": 0.0, "water": 0.0, "carbon": 0.0,
        "sessions": set(),
    })
    for e in entries:
        b = buckets[e[key]]
        b["turns"] += 1
        b["inp"]   += e["inp"]
        b["out"]   += e["out"]
        b["cw"]    += e["cw"]
        b["cr"]    += e["cr"]
        b["cost"]  += calc_cost(e["model"], e["inp"], e["out"], e["cw"], e["cr"])
        nrg, wat, co2 = calc_env(e["inp"], e["out"], e["cw"], e["cr"])
        b["energy"] += nrg
        b["water"]  += wat
        b["carbon"] += co2
        b["sessions"].add(e["session"])
    return buckets


def fmt_tok(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def fmt_wh(kwh):
    wh = kwh * 1000
    if wh >= 1000:
        return f"{kwh:.3f}kWh"
    if wh >= 1:
        return f"{wh:.1f}Wh"
    return f"{wh*1000:.1f}mWh"


def fmt_water(l):
    if l >= 1:
        return f"{l:.2f}L"
    return f"{l*1000:.1f}mL"


def fmt_carbon(kg):
    if kg >= 1:
        return f"{kg:.3f}kg"
    return f"{kg*1000:.1f}g"


def _car_km(carbon_kg):
    return carbon_kg / 0.21   # 0.21 kg CO2/km, EU average petrol car


def _fmt_duration(hours):
    """Express a fractional hour count as a natural string."""
    if hours < 1/60:
        return f"{hours*3600:.0f} seconds"
    if hours < 1:
        return f"{hours*60:.0f} minutes"
    if hours < 24:
        return f"{hours:.1f} hours"
    return f"{hours/24:.1f} days"


def print_env_analogs(kwh, water_l):
    lighting_h = kwh / LED_HOUSE_KW
    lighting_d = lighting_h / LED_HOURS_PER_DAY
    meals      = kwh / MEAL_KWH

    # Lighting line
    if lighting_h < 1:
        light_qty = f"{lighting_h*60:.0f} minutes"
    elif lighting_d < 1:
        light_qty = f"{lighting_h:.1f} hours"
    else:
        light_qty = f"{lighting_d:.1f} days ({lighting_h:.0f} hrs)"
    light_note = f"8 × 9W LED bulbs, 800 sq ft / 2-room house, {LED_HOURS_PER_DAY:.0f}h/day use"

    # Water line — volume of cooling water evaporated, compared to everyday volumes
    if water_l < WATER_GLASS_L:
        water_qty  = f"{water_l*1000:.0f} mL"
        water_note = "of data-center cooling water evaporated (< 1 glass)"
    elif water_l < WATER_SHOWER_L:
        glasses    = water_l / WATER_GLASS_L
        water_qty  = f"{glasses:.1f} glasses (250 mL each)"
        water_note = f"of data-center cooling water evaporated; WUE {WUE_L_PER_KWH} L/kWh (Li et al. 2023)"
    else:
        showers    = water_l / WATER_SHOWER_L
        water_qty  = f"{showers:.1f} × 8-min showers"
        water_note = f"of data-center cooling water evaporated; WUE {WUE_L_PER_KWH} L/kWh (Li et al. 2023)"

    # Cooking line
    if meals < 1:
        cook_qty = f"{meals*60:.0f} minutes"
    else:
        cook_qty = f"{meals:.1f} meals"
    cook_note = "30-min meal on a single 1 kW electric burner"

    print(f"\n  Real-world equivalents:")
    print(f"    Lighting  {light_qty}")
    print(f"              ({light_note})")
    print(f"    Water     {water_qty}")
    print(f"              ({water_note})")
    print(f"    Cooking   {cook_qty} cooked on electric stove")
    print(f"              ({cook_note})")


def print_table(buckets, label_header, show_env=False):
    rows = sorted(buckets.items(), key=lambda x: x[0])
    col_w = max((len(k) for k in buckets), default=10)
    col_w = max(col_w, len(label_header))

    if show_env:
        h = f"{'─'*(col_w+2)}┬{'─'*8}┬{'─'*9}┬{'─'*9}┬{'─'*10}┬{'─'*10}┬{'─'*11}"
        print(f"\n  {label_header:<{col_w}}  │ Turns  │   Input  │  Output  │  Energy   │   Water   │  CO2")
        print(f"  {h}")
        totals = {"turns":0,"inp":0,"out":0,"energy":0.0,"water":0.0,"carbon":0.0,"sessions":set()}
        for key, b in rows:
            label = key if len(key) <= col_w else "…" + key[-(col_w-1):]
            print(f"  {label:<{col_w}}  │ {b['turns']:>5}  │ {fmt_tok(b['inp']):>7}  │ {fmt_tok(b['out']):>7}  │ {fmt_wh(b['energy']):>9}  │ {fmt_water(b['water']):>9}  │ {fmt_carbon(b['carbon'])}")
            for k in ("turns","inp","out","energy","water","carbon"):
                totals[k] += b[k]
            totals["sessions"] |= b["sessions"]
        print(f"  {h.replace('┬','┴')}")
        print(f"  {'TOTAL':<{col_w}}  │ {totals['turns']:>5}  │ {fmt_tok(totals['inp']):>7}  │ {fmt_tok(totals['out']):>7}  │ {fmt_wh(totals['energy']):>9}  │ {fmt_water(totals['water']):>9}  │ {fmt_carbon(totals['carbon'])}")
        print_env_analogs(totals["energy"], totals["water"])
        print()
    else:
        h = f"{'─'*(col_w+2)}┬{'─'*8}┬{'─'*9}┬{'─'*9}┬{'─'*9}┬{'─'*9}┬{'─'*10}┬{'─'*9}"
        print(f"\n  {label_header:<{col_w}}  │ Turns  │   Input  │  Output  │CacheWrt │CacheRd  │ ~Cost($) │Sessions")
        print(f"  {h}")
        totals = {"turns":0,"inp":0,"out":0,"cw":0,"cr":0,"cost":0.0,"sessions":set()}
        for key, b in rows:
            label = key if len(key) <= col_w else "…" + key[-(col_w-1):]
            print(f"  {label:<{col_w}}  │ {b['turns']:>5}  │ {fmt_tok(b['inp']):>7}  │ {fmt_tok(b['out']):>7}  │ {fmt_tok(b['cw']):>6}  │ {fmt_tok(b['cr']):>6}  │ {b['cost']:>8.4f} │ {len(b['sessions']):>6}")
            for k in ("turns","inp","out","cw","cr"):
                totals[k] += b[k]
            totals["cost"]     += b["cost"]
            totals["sessions"] |= b["sessions"]
        print(f"  {h.replace('┬','┴')}")
        print(f"  {'TOTAL':<{col_w}}  │ {totals['turns']:>5}  │ {fmt_tok(totals['inp']):>7}  │ {fmt_tok(totals['out']):>7}  │ {fmt_tok(totals['cw']):>6}  │ {fmt_tok(totals['cr']):>6}  │ {totals['cost']:>8.4f} │ {len(totals['sessions']):>6}\n")


def print_summary(entries, show_env=False):
    if not entries:
        print("No usage data found.")
        return
    total_inp    = sum(e["inp"] for e in entries)
    total_out    = sum(e["out"] for e in entries)
    total_cw     = sum(e["cw"]  for e in entries)
    total_cr     = sum(e["cr"]  for e in entries)
    total_cost   = sum(calc_cost(e["model"], e["inp"], e["out"], e["cw"], e["cr"]) for e in entries)
    total_energy, total_water, total_carbon = calc_env(total_inp, total_out, total_cw, total_cr)
    sessions     = len({e["session"] for e in entries})
    models       = {}
    for e in entries:
        models[e["model"]] = models.get(e["model"], 0) + 1

    print(f"\n  claudia — Claude Introspective Analysis")
    print(f"  {'─'*40}")
    print(f"  Period:        {entries[0]['date']} → {entries[-1]['date']}")
    print(f"  Turns:         {len(entries):,}")
    print(f"  Sessions:      {sessions:,}")
    print(f"  Input tokens:  {fmt_tok(total_inp)}")
    print(f"  Output tokens: {fmt_tok(total_out)}")
    print(f"  Cache writes:  {fmt_tok(total_cw)}")
    print(f"  Cache reads:   {fmt_tok(total_cr)}")
    print(f"  Est. cost:     ${total_cost:.4f}")

    print(f"\n  Environmental Impact  (estimated)")
    print(f"  {'─'*40}")
    print(f"  Energy:        {fmt_wh(total_energy)}")
    print(f"  Water:         {fmt_water(total_water)}")
    print(f"  Carbon:        {fmt_carbon(total_carbon)}")
    print(f"  ≈ driving      {_car_km(total_carbon):.1f} km in an average car")
    print_env_analogs(total_energy, total_water)

    print(f"\n  Models:")
    for m, c in sorted(models.items(), key=lambda x: -x[1]):
        print(f"    {m}: {c:,} turns")
    print()


def _api_get(admin_key, path, params):
    """Single paginated fetch from the Anthropic Admin API, returning all results."""
    base = "https://api.anthropic.com" + path
    results = []
    page = None
    while True:
        p = dict(params)
        if page:
            p["page"] = page
        url = base + "?" + urllib.parse.urlencode(p, doseq=True)
        req = urllib.request.Request(url, headers={
            "x-api-key":          admin_key,
            "anthropic-version":  "2023-06-01",
            "content-type":       "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            print(f"\n  API error {e.code}: {msg}", file=sys.stderr)
            sys.exit(1)
        for bucket in body.get("data", []):
            results.extend(bucket.get("results", []))
        if not body.get("has_more"):
            break
        page = body.get("next_page")
    return results


def cmd_verify(entries, api_key_ids=None):
    admin_key = os.environ.get("ANTHROPIC_ADMIN_KEY", "")
    if not admin_key:
        print("\n  ANTHROPIC_ADMIN_KEY env var not set.")
        print("  Set it to an Admin API key (sk-ant-admin...) from console.anthropic.com.")
        sys.exit(1)

    if not entries:
        print("No local usage data to verify against.")
        sys.exit(0)

    # Date range from local data, rounded to day boundaries
    start_dt = entries[0]["ts"][:10] + "T00:00:00Z"
    # end is tomorrow so today's data is included
    end_dt   = entries[-1]["ts"][:10]
    end_date = datetime.fromisoformat(end_dt)
    from datetime import timedelta
    end_dt   = (end_date + timedelta(days=1)).strftime("%Y-%m-%d") + "T00:00:00Z"

    print(f"\n  Fetching API usage {start_dt[:10]} → {entries[-1]['ts'][:10]} ...")

    params = {
        "starting_at":  start_dt,
        "ending_at":    end_dt,
        "bucket_width": "1d",
        "group_by[]":   ["model", "api_key_id"],
        "limit":        31,
    }
    if api_key_ids:
        params["api_key_ids[]"] = api_key_ids

    results = _api_get(admin_key, "/v1/organizations/usage_report/messages", params)

    # Aggregate API totals by model
    api_by_model = defaultdict(lambda: {"inp": 0, "out": 0, "cw": 0, "cr": 0})
    api_total    = {"inp": 0, "out": 0, "cw": 0, "cr": 0}
    for r in results:
        m   = r.get("model", "unknown")
        inp = r.get("uncached_input_tokens", 0)
        out = r.get("output_tokens", 0)
        cr  = r.get("cache_read_input_tokens", 0)
        cw  = (r.get("cache_creation", {}) or {}).get("ephemeral_1h_input_tokens", 0) + \
              (r.get("cache_creation", {}) or {}).get("ephemeral_5m_input_tokens", 0)
        for d, v in (("inp", inp), ("out", out), ("cw", cw), ("cr", cr)):
            api_by_model[m][d] += v
            api_total[d]       += v

    # Aggregate local totals by model
    local_by_model = defaultdict(lambda: {"inp": 0, "out": 0, "cw": 0, "cr": 0})
    local_total    = {"inp": 0, "out": 0, "cw": 0, "cr": 0}
    for e in entries:
        m = e["model"]
        for d in ("inp", "out", "cw", "cr"):
            local_by_model[m][d] += e[d]
            local_total[d]       += e[d]

    # Print comparison
    all_models = sorted(set(list(api_by_model) + list(local_by_model)))
    col = max((len(m) for m in all_models), default=10, )
    col = max(col, 5)

    def delta(a, b):
        d = a - b
        return f"+{d:,}" if d > 0 else f"{d:,}" if d < 0 else "="

    print(f"\n  API vs Local — token comparison")
    print(f"  {'─'*72}")
    print(f"  {'Model':<{col}}  {'':>4}  {'Input':>10}  {'Output':>10}  {'CacheWrt':>10}  {'CacheRd':>10}")
    print(f"  {'─'*72}")

    for m in all_models:
        a = api_by_model[m]
        l = local_by_model[m]
        print(f"  {m:<{col}}  {'API':>4}  {fmt_tok(a['inp']):>10}  {fmt_tok(a['out']):>10}  {fmt_tok(a['cw']):>10}  {fmt_tok(a['cr']):>10}")
        print(f"  {'':>{col}}  {'local':>4}  {fmt_tok(l['inp']):>10}  {fmt_tok(l['out']):>10}  {fmt_tok(l['cw']):>10}  {fmt_tok(l['cr']):>10}")
        print(f"  {'':>{col}}  {'Δ':>4}  {delta(a['inp'], l['inp']):>10}  {delta(a['out'], l['out']):>10}  {delta(a['cw'], l['cw']):>10}  {delta(a['cr'], l['cr']):>10}")
        print()

    print(f"  {'─'*72}")
    print(f"  {'TOTAL':<{col}}  {'API':>4}  {fmt_tok(api_total['inp']):>10}  {fmt_tok(api_total['out']):>10}  {fmt_tok(api_total['cw']):>10}  {fmt_tok(api_total['cr']):>10}")
    print(f"  {'':>{col}}  {'local':>4}  {fmt_tok(local_total['inp']):>10}  {fmt_tok(local_total['out']):>10}  {fmt_tok(local_total['cw']):>10}  {fmt_tok(local_total['cr']):>10}")
    print(f"  {'':>{col}}  {'Δ':>4}  {delta(api_total['inp'], local_total['inp']):>10}  {delta(api_total['out'], local_total['out']):>10}  {delta(api_total['cw'], local_total['cw']):>10}  {delta(api_total['cr'], local_total['cr']):>10}")

    if api_key_ids:
        print(f"\n  Filtered to API key(s): {', '.join(api_key_ids)}")
    else:
        print(f"\n  Note: API totals are org-wide. Use --api-key-id to filter to your key.")
    print()


# ── web dashboard ─────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>claudia</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",monospace;
      background:#0d1117;color:#c9d1d9;padding:24px;min-height:100vh}
    h1{font-size:1.1rem;color:#58a6ff}
    .sub{font-size:.75rem;color:#8b949e;margin-top:3px;margin-bottom:20px}
    .cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
    .card{background:#161b22;border:1px solid #30363d;border-radius:8px;
      padding:14px 18px;min-width:130px}
    .card .val{font-size:1.4rem;font-weight:700;color:#f0f6fc}
    .card .lbl{font-size:.68rem;color:#8b949e;text-transform:uppercase;
      letter-spacing:.05em;margin-top:2px}
    .panel{background:#161b22;border:1px solid #30363d;border-radius:8px;
      padding:16px 18px;margin-bottom:16px}
    .panel h2{font-size:.72rem;color:#8b949e;text-transform:uppercase;
      letter-spacing:.07em;margin-bottom:14px}
    .bar-row{display:flex;align-items:center;margin-bottom:6px}
    .bar-lbl{width:180px;flex-shrink:0;font-size:.76rem;white-space:nowrap;
      overflow:hidden;text-overflow:ellipsis;text-align:right;padding-right:10px}
    .bar-track{flex:1;height:18px;background:#21262d;border-radius:3px;
      position:relative;overflow:hidden}
    .bar-fill{height:100%;background:#1f6feb;border-radius:3px;transition:width .3s}
    .bar-val{position:absolute;right:6px;top:50%;transform:translateY(-50%);
      font-size:.71rem;color:#e2e8f0}
    .mchart{display:flex;align-items:flex-end;gap:6px;height:100px}
    .mcol{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px}
    .mbar{width:100%;background:#1f6feb;border-radius:3px 3px 0 0;min-height:2px}
    .mname{font-size:.68rem;color:#8b949e}
    .mcost{font-size:.68rem;color:#c9d1d9}
    table{width:100%;border-collapse:collapse;font-size:.78rem}
    th{padding:4px 8px;text-align:left;color:#8b949e;font-weight:500;
      border-bottom:1px solid #21262d}
    td{padding:5px 8px;border-bottom:1px solid #21262d}
    tr:last-child td{border-bottom:none}
    .envrow{display:flex;gap:24px;flex-wrap:wrap}
    .envitem .val{font-size:1.05rem;font-weight:600;color:#3fb950}
    .envitem .lbl{font-size:.68rem;color:#8b949e;margin-top:2px}
    .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
    footer{font-size:.7rem;color:#484f58;text-align:center;margin-top:8px}
    @media(max-width:680px){.grid2{grid-template-columns:1fr}.bar-lbl{width:90px}}
  </style>
</head>
<body>
<h1>claudia &#8212; Claude Introspective Analysis</h1>
<div class="sub" id="sub">Loading...</div>
<div class="cards" id="cards"></div>
<div class="panel"><h2>Cost by project</h2><div id="proj"></div></div>
<div class="grid2">
  <div class="panel"><h2>Monthly spend</h2><div id="months"></div></div>
  <div class="panel"><h2>Models</h2><div id="models"></div></div>
</div>
<div class="panel"><h2>Environmental impact (estimated)</h2><div id="env"></div></div>
<footer id="footer"></footer>
<script>
const G=id=>document.getElementById(id);
function fmtTok(n){return n>=1e6?(n/1e6).toFixed(2)+"M":n>=1e3?(n/1e3).toFixed(1)+"K":""+n}
function bars(rows,maxV){
  return rows.map(r=>{
    const pct=Math.max(2,r.v/maxV*100).toFixed(1);
    const lbl=r.l.split("/").filter(Boolean).pop()||r.l;
    return "<div class=\\"bar-row\\"><span class=\\"bar-lbl\\" title=\\""+r.l+"\\">"+lbl+"</span>"+
      "<div class=\\"bar-track\\"><div class=\\"bar-fill\\" style=\\"width:"+pct+"%\\"></div>"+
      "<span class=\\"bar-val\\">"+r.d+"</span></div></div>";
  }).join("");
}
async function load(){
  let d;
  try{d=await fetch("/api/data").then(r=>r.json());}
  catch(e){G("sub").textContent="Error: "+e;return;}
  const s=d.summary;
  G("sub").textContent=s.period_start+" to "+s.period_end+"  ·  refreshes every 60s";
  G("cards").innerHTML=[
    ["$"+s.cost.toFixed(2),"Est. Cost"],
    [s.turns.toLocaleString(),"Turns"],
    [s.sessions.toLocaleString(),"Sessions"],
    [fmtTok(s.inp+s.cw+s.cr+s.out),"Total Tokens"],
    [s.energy_kwh.toFixed(3)+" kWh","Energy"],
    [s.carbon_kg.toFixed(3)+" kg","CO2"],
  ].map(([v,l])=>"<div class=\\"card\\"><div class=\\"val\\">"+v+"</div><div class=\\"lbl\\">"+l+"</div></div>").join("");
  const proj=d.by_project.slice(0,12),maxP=Math.max(...proj.map(p=>p.cost),.01);
  G("proj").innerHTML=bars(proj.map(p=>({l:p.label,v:p.cost,d:"$"+p.cost.toFixed(2)})),maxP);
  const mons=d.by_month,maxM=Math.max(...mons.map(m=>m.cost),.01);
  G("months").innerHTML="<div class=\\"mchart\\">"+mons.map(m=>"<div class=\\"mcol\\">"+
    "<span class=\\"mcost\\">$"+m.cost.toFixed(0)+"</span>"+
    "<div class=\\"mbar\\" style=\\"height:"+Math.max(2,m.cost/maxM*80).toFixed(0)+"px\\"></div>"+
    "<span class=\\"mname\\">"+m.label.slice(5)+"</span></div>").join("")+"</div>";
  G("models").innerHTML="<table><thead><tr><th>Model</th><th>Turns</th><th>Cost</th></tr></thead><tbody>"+
    d.by_model.map(m=>"<tr><td>"+m.label.replace("claude-","")+"</td>"+
    "<td>"+m.turns.toLocaleString()+"</td><td>$"+m.cost.toFixed(2)+"</td></tr>").join("")+"</tbody></table>";
  G("env").innerHTML="<div class=\\"envrow\\">"+[
    [s.energy_kwh.toFixed(3)+" kWh","Energy"],
    [s.water_l.toFixed(2)+" L","Water"],
    [s.carbon_kg.toFixed(3)+" kg","CO2"],
    [(s.carbon_kg/0.21).toFixed(1)+" km","Driving equiv."],
  ].map(([v,l])=>"<div class=\\"envitem\\"><div class=\\"val\\">"+v+"</div><div class=\\"lbl\\">"+l+"</div></div>").join("")+"</div>";
  G("footer").textContent="Last updated: "+new Date().toLocaleTimeString();
}
load();setInterval(load,60000);
</script>
</body>
</html>"""


def build_api_data(entries: list) -> dict:
    if not entries:
        return {"error": "no data"}
    total_inp  = sum(e["inp"] for e in entries)
    total_out  = sum(e["out"] for e in entries)
    total_cw   = sum(e["cw"]  for e in entries)
    total_cr   = sum(e["cr"]  for e in entries)
    total_cost = sum(calc_cost(e["model"], e["inp"], e["out"], e["cw"], e["cr"]) for e in entries)
    energy, water, carbon = calc_env(total_inp, total_out, total_cw, total_cr)
    sessions = len({e["session"] for e in entries})

    def blist(key: str, sort_key: str = "cost") -> list:
        rows = []
        for k, b in aggregate(entries, key).items():
            rows.append({
                "label":    k,
                "turns":    b["turns"],
                "cost":     round(b["cost"], 4),
                "inp":      b["inp"],
                "out":      b["out"],
                "cw":       b["cw"],
                "cr":       b["cr"],
                "sessions": len(b["sessions"]),
            })
        return sorted(rows, key=lambda r: -r[sort_key])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "period_start": entries[0]["date"],
            "period_end":   entries[-1]["date"],
            "turns":        len(entries),
            "sessions":     sessions,
            "cost":         round(total_cost, 4),
            "inp":          total_inp,
            "out":          total_out,
            "cw":           total_cw,
            "cr":           total_cr,
            "energy_kwh":   round(energy, 4),
            "water_l":      round(water, 3),
            "carbon_kg":    round(carbon, 4),
        },
        "by_project": blist("project"),
        "by_month":   sorted(blist("month"), key=lambda r: r["label"]),
        "by_model":   blist("model"),
    }


def _make_handler(since, project_filter, model_filter=None):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/data":
                data = build_api_data(load_entries(since=since, project_filter=project_filter, model_filter=model_filter))
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def log_message(self, fmt, *args):
            pass  # suppress per-request noise

    return Handler


def cmd_serve(since, project_filter, port: int, model_filter: str | None = None) -> None:
    handler = _make_handler(since, project_filter, model_filter)
    server  = http.server.HTTPServer(("", port), handler)
    print(f"\n  claudia dashboard  →  http://localhost:{port}/")
    print(f"  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print("\n  Server stopped.")


def cmd_snapshot(entries: list) -> None:
    snap_dir = pathlib.Path.home() / ".claude" / "claudia-snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = snap_dir / f"{today}.json"
    data     = build_api_data(entries)
    out_file.write_text(json.dumps(data, indent=2))
    s = data.get("summary", {})
    print(f"  Snapshot  →  {out_file}")
    print(f"  Cost: ${s.get('cost', 0):.4f}  Turns: {s.get('turns', 0):,}")


# ── export ────────────────────────────────────────────────────────────────────

def cmd_export(entries: list, fmt: str, by: str | None) -> None:
    if fmt == "json":
        print(json.dumps(build_api_data(entries), indent=2))
        return
    key    = {"project": "project", "day": "date", "week": "week", "month": "month"}.get(by or "project", "project")
    header = {"project": "Project", "date": "Date", "week": "Week", "month": "Month"}[key]
    w = csv.writer(sys.stdout)
    w.writerow([header, "turns", "inp", "out", "cw", "cr", "cost_usd", "energy_kwh", "sessions"])
    for k, b in sorted(aggregate(entries, key).items()):
        w.writerow([k, b["turns"], b["inp"], b["out"], b["cw"], b["cr"],
                    f"{b['cost']:.6f}", f"{b['energy']:.6f}", len(b["sessions"])])


# ── live watch ────────────────────────────────────────────────────────────────

def cmd_watch(since: str | None, project_filter: str | None, interval: int, model_filter: str | None = None) -> None:
    try:
        while True:
            entries = load_entries(since=since, project_filter=project_filter, model_filter=model_filter)
            os.system("clear")
            if entries:
                print_summary(entries)
            else:
                print("  No usage data found.")
            now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            print(f"  ── refreshing every {interval}s  (Ctrl+C to stop)  [{now}]")
            time.sleep(interval)
    except KeyboardInterrupt:
        print()


# ── delta view ────────────────────────────────────────────────────────────────

def cmd_delta(entries: list, period: str) -> None:
    key   = {"week": "week", "month": "month"}[period]
    label = {"week": "Week", "month": "Month"}[period]
    rows  = sorted(aggregate(entries, key).items())
    col_w = max((len(k) for k in dict(rows)), default=6)
    col_w = max(col_w, len(label))

    def dcost(v: float) -> str:
        return f"+${v:.2f}" if v > 0 else (f"-${abs(v):.2f}" if v < 0 else "=")

    def dint(v: int) -> str:
        return f"+{v}" if v > 0 else (str(v) if v < 0 else "=")

    print(f"\n  {label:<{col_w}}  │ ~Cost($) │  ΔCost   │    Δ%  │ Turns │ ΔTurns")
    print(f"  {'─'*(col_w+2)}┬{'─'*10}┬{'─'*10}┬{'─'*8}┬{'─'*7}┬{'─'*8}")
    for i, (k, b) in enumerate(rows):
        if i == 0:
            dc = dt = pct = ""
        else:
            prev  = rows[i - 1][1]
            dc_v  = b["cost"]  - prev["cost"]
            dt_v  = b["turns"] - prev["turns"]
            pct_v = (dc_v / prev["cost"] * 100) if prev["cost"] else 0
            dc    = dcost(dc_v)
            dt    = dint(dt_v)
            pct   = f"+{pct_v:.0f}%" if pct_v >= 0 else f"{pct_v:.0f}%"
        print(f"  {k:<{col_w}}  │ {b['cost']:>8.4f} │ {dc:>8} │ {pct:>6} │ {b['turns']:>5} │ {dt:>6}")
    print()


# ── cost breakdown ─────────────────────────────────────────────────────────────

def cmd_cost(entries: list) -> None:
    by_model = aggregate(entries, "model")
    total    = sum(b["cost"] for b in by_model.values())
    print(f"\n  Cost breakdown  ({entries[0]['date']} → {entries[-1]['date']})")
    print(f"  {'─'*60}")
    for model, b in sorted(by_model.items(), key=lambda x: -x[1]["cost"]):
        p   = PRICING.get(model, DEFAULT_PRICING)
        pct = b["cost"] / total * 100 if total else 0
        print(f"\n  {model}  ${b['cost']:.4f}  ({pct:.1f}%)")
        for field, lbl, price in (
            ("inp", "inp  ", p[0]), ("out", "out  ", p[1]),
            ("cw",  "cw   ", p[2]), ("cr",  "cr   ", p[3]),
        ):
            n = b[field]
            if n:
                print(f"    {lbl}  {fmt_tok(n):>9} tokens  × ${price:>5.2f}/M  =  ${n*price/1_000_000:>9.4f}")
    print(f"\n  {'─'*60}")
    print(f"  TOTAL  ${total:.4f}\n")


# ── admin API key list ─────────────────────────────────────────────────────────

def _api_list(admin_key: str, path: str, params: dict) -> list:
    """Paginated fetch for flat-list Admin API endpoints."""
    base  = "https://api.anthropic.com" + path
    items = []
    after = None
    while True:
        p = dict(params)
        if after:
            p["after_id"] = after
        url = base + "?" + urllib.parse.urlencode(p)
        req = urllib.request.Request(url, headers={
            "x-api-key":         admin_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            print(f"\n  API error {e.code}: {msg}", file=sys.stderr)
            sys.exit(1)
        data = body.get("data", [])
        items.extend(data)
        if not body.get("has_more") or not data:
            break
        after = data[-1].get("id")
    return items


def cmd_keys() -> None:
    admin_key = os.environ.get("ANTHROPIC_ADMIN_KEY", "")
    if not admin_key:
        print("\n  ANTHROPIC_ADMIN_KEY env var not set.", file=sys.stderr)
        sys.exit(1)
    print("\n  Fetching API keys ...")
    keys = _api_list(admin_key, "/v1/organizations/api_keys", {"limit": 100})
    if not keys:
        print("  No API keys found.")
        return
    col = max((len(k.get("name", "")) for k in keys), default=4)
    col = max(col, 4)
    print(f"\n  {'Name':<{col}}  {'ID':<36}  Status")
    print(f"  {'─'*(col+2)}┬{'─'*38}┬{'─'*10}")
    for k in keys:
        print(f"  {k.get('name',''):<{col}}  {k.get('id','?'):<36}  {k.get('status','?')}")
    print(f"\n  Pass an ID above to --api-key-id with --verify.\n")


def cmd_install_cron() -> None:
    entry = "0 8 * * * /usr/local/bin/claudia --snapshot >> ~/.claude/claudia-monitor.log 2>&1"
    try:
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        print("  crontab not found — install cron (e.g. apt install cron) and retry.", file=sys.stderr)
        sys.exit(1)
    if "claudia --snapshot" in current:
        print("  Daily snapshot job already installed.")
        return
    new_tab = current.rstrip("\n") + ("\n" if current else "") + entry + "\n"
    result  = subprocess.run(["crontab", "-"], input=new_tab, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Installed: {entry}")
        print(f"  Snapshots saved to ~/.claude/claudia-snapshots/YYYY-MM-DD.json")
    else:
        print(f"  crontab error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="claudia",
        description=(
            "claudia — Claude Introspective Analysis\n"
            "Reports token usage, estimated cost, and environmental impact\n"
            "from your local Claude Code session logs (~/.claude/projects/).\n\n"
            "Intended to expand into a broader suite of Claude self-analysis tools."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--by", choices=["project", "day", "week", "month"],
                        help="Group results by project, day, week, or month")
    parser.add_argument("--since", metavar="YYYY-MM-DD",
                        help="Only include usage on or after this date")
    parser.add_argument("--project", metavar="PATH",
                        help="Filter to a project path (substring match)")
    parser.add_argument("--model", metavar="NAME",
                        help="Filter to a model name (substring match, e.g. opus, sonnet, haiku)")
    parser.add_argument("--models", action="store_true",
                        help="Show a model breakdown table")
    parser.add_argument("--env", action="store_true",
                        help="Show estimated energy, water, and carbon impact")
    parser.add_argument("--verify", action="store_true",
                        help="Cross-check local totals against the Anthropic Admin API "
                             "(requires ANTHROPIC_ADMIN_KEY env var)")
    parser.add_argument("--api-key-id", metavar="KEY_ID", action="append", dest="api_key_ids",
                        help="Filter API verify to this key ID (repeatable); "
                             "e.g. apikey_01Abc... — find IDs at console.anthropic.com")
    parser.add_argument("--serve", action="store_true",
                        help="Start a local web dashboard")
    parser.add_argument("--port", type=int, default=7777, metavar="PORT",
                        help="Port for --serve (default: 7777)")
    parser.add_argument("--snapshot", action="store_true",
                        help="Save a JSON snapshot to ~/.claude/claudia-snapshots/YYYY-MM-DD.json")
    parser.add_argument("--install-cron", action="store_true",
                        help="Install a daily cron job (08:00) to run --snapshot")
    parser.add_argument("--export", choices=["json", "csv"], metavar="{json,csv}",
                        help="Export data as JSON or CSV (combines with --by for CSV grouping)")
    parser.add_argument("--watch", action="store_true",
                        help="Live mode: reprint summary every --interval seconds")
    parser.add_argument("--interval", type=int, default=5, metavar="SEC",
                        help="Refresh interval for --watch in seconds (default: 5)")
    parser.add_argument("--delta", choices=["week", "month"], metavar="{week,month}",
                        help="Show period-over-period cost and turn delta")
    parser.add_argument("--cost", action="store_true",
                        help="Detailed cost breakdown by model and token type")
    parser.add_argument("--keys", action="store_true",
                        help="List API key IDs from the Admin API (requires ANTHROPIC_ADMIN_KEY)")
    args = parser.parse_args()

    since_ts = (args.since + "T00:00:00Z") if args.since else None

    if args.install_cron:
        cmd_install_cron()
        return

    if args.keys:
        cmd_keys()
        return

    if args.serve:
        cmd_serve(since_ts, args.project, args.port, model_filter=args.model)
        return

    if args.watch:
        cmd_watch(since_ts, args.project, args.interval, model_filter=args.model)
        return

    entries = load_entries(since=since_ts, project_filter=args.project, model_filter=args.model)

    if not entries:
        print("No matching usage data found.")
        sys.exit(0)

    if args.export:
        cmd_export(entries, args.export, args.by)
    elif args.snapshot:
        cmd_snapshot(entries)
    elif args.delta:
        cmd_delta(entries, args.delta)
    elif args.cost:
        cmd_cost(entries)
    elif args.verify:
        cmd_verify(entries, api_key_ids=args.api_key_ids)
    elif args.by:
        key   = {"project": "project", "day": "date", "week": "week", "month": "month"}[args.by]
        label = {"project": "Project",  "day": "Date", "week": "Week", "month": "Month"}[args.by]
        print_table(aggregate(entries, key), label, show_env=args.env)
    elif args.models:
        print_table(aggregate(entries, "model"), "Model", show_env=args.env)
    else:
        print_summary(entries, show_env=args.env)


if __name__ == "__main__":
    main()
