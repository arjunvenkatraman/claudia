# ADR-002: Environmental impact estimation methodology

**Status:** Accepted

## Context

Users want to see energy, water, and carbon estimates alongside token usage. Anthropic does
not publish per-token energy or emissions metrics. Estimates must be derived from third-party
research and clearly labelled as approximations.

Three quantities are estimated: energy (kWh), water (litres), and carbon (kg CO2).

## Decision

### Energy per token (Joules — IT equipment only)

Source: **TokenPowerBench** (arxiv 2512.03024) and **Luccioni et al. 2023** ("Power Hungry
Processing", ACL). Decode/prefill cost split from **Agrawal et al. 2024** (OSDI). Values
reflect large-parameter (50B+) model inference on H100-class hardware.

| Token type | Joules | Rationale |
|---|---|---|
| Output (decode) | 0.39 | One full forward pass per token — compute-bound, autoregressive |
| Input (prefill) | 0.13 | Single forward pass over all tokens at once |
| Cache write | 0.13 | Same compute as prefill; KV activations written to HBM |
| Cache read | 0.02 | KV retrieval from HBM — memory-bandwidth-bound, no matmul |

Output tokens dominate because each requires an independent forward pass. Uncertainty is
±50% given model size is undisclosed; treat as order-of-magnitude.

### Power Usage Effectiveness (PUE)

Source: **Google ESG Report 2023**; **Masanet et al. 2020** (Science).

**PUE = 1.12** — ratio of total data-center facility energy to IT equipment energy.
Applied to the carbon calculation only (grid draws IT × PUE). Not applied to the energy
figure shown to the user (which reflects compute energy for direct appliance comparison).

Reference points: Google global avg 2023: 1.10; AWS estimated: 1.15; industry avg: 1.58.
Using 1.12 as a conservative hyperscaler estimate (Anthropic runs on AWS/GCP infrastructure).

### Water per IT kWh (Water Usage Effectiveness — WUE)

Source: **Li et al. 2023** ("Making AI Less Thirsty", arxiv 2304.03271).

**WUE = 1.8 L/kWh** — liters of cooling water physically evaporated in data-center cooling
towers per IT equipment kWh consumed. This is water consumption, not the energy cost of
pumping water.

Provider range per Li et al. 2023: 0.49 L/kWh (Microsoft) to 1.80 L/kWh (industry avg).
Using the industry average as the conservative, verifiable choice given uncertainty about
Anthropic's exact infrastructure mix.

The real-world analog compares this volume directly to everyday water quantities (glasses,
showers) — not to pumping energy.

### Carbon per kWh

Source: **US EPA / Ember, 2024 grid data**.

**0.384 kg CO2/kWh** — US grid average. Applied to total facility energy (IT × PUE), since
the grid supplies power for both compute and cooling. Anthropic primarily operates in US data
centers. AWS has renewable energy commitments that would lower this; the US average is the
conservative, publicly verifiable choice.

### Real-world analogs

| Analog | Value | Source |
|---|---|---|
| LED house lighting | 72W (8 × 9W bulbs, 800 sq ft / 2 rooms) | Standard residential lighting design |
| Water consumed | compared by volume: glasses (250 mL), 8-min showers (65 L) | US EPA WaterSense |
| Cooking a meal | 0.5 kWh (30 min, 1 kW electric burner) | Standard electric hob rating |
| Driving | 0.21 kg CO2/km | EU average petrol car |

## Consequences

- All estimates are approximations. Actual values vary significantly by hardware generation,
  batch size, data-center location, and grid mix.
- The output clearly labels the section "estimated" and the `--help` text links to this ADR.
- Constants are grouped at the top of `claudia` and annotated with sources for easy updating.
- Carbon estimates are ~12% higher than before PUE was added — this is more accurate.
- When Anthropic publishes official per-token figures, replace the TokenPowerBench values.
